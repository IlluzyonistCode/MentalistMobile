import frida
import frida_bridge
import frida_tools
import threading
import os
import sys
import time
import traceback
from datetime import datetime
from colorama import Fore, Style, init
import config
from auth_protection import _integrity_checker
from utils import get_time, banner, load_script, wrap_user_script, build_final_script, create_message_queue_wrapper
from backend import Backend

init(autoreset=True)

print(
	f'{datetime.now().strftime("[%H:%M:%S]")} {Fore.GREEN}Loaded config.txt{Style.RESET_ALL}',
	flush=True
)

_integrity_checker.verify_integrity()

if __name__ == '__main__':
	try:
		banner()

		if not frida_bridge.authenticate_mobile():
			print(
				f'{get_time()} {Fore.RED}Authentication required. Exiting.{Style.RESET_ALL}',
				flush=True
			)

			sys.exit(1)

		time_str = get_time()

		print(f'{time_str} {Fore.WHITE}Waiting for device connection...{Style.RESET_ALL}', flush=True)

		if config.DEVICE_SERIAL:
			try:
				device = frida.get_device(config.DEVICE_SERIAL)
			except Exception:
				print(
					f'{time_str} {Fore.YELLOW}Failed to connect to {config.DEVICE_SERIAL}, trying USB...{Style.RESET_ALL}',
					flush=True
				)

				device = frida.get_usb_device(timeout=10)

		else:
			try:
				device = frida.get_usb_device(timeout=10)
			except Exception:
				print(
					f'{time_str} {Fore.YELLOW}No USB device, trying network...{Style.RESET_ALL}',
					flush=True
				)

				devices = frida.enumerate_devices()

				if devices:
					device = devices[0]

					print(f'{time_str} {Fore.GREEN}Found: {device.name}{Style.RESET_ALL}', flush=True)

				else:
					raise Exception('No devices available (USB or network)')

		print(f'{get_time()} {Fore.GREEN}Device connected: {device.name}{Style.RESET_ALL}', flush=True)

		print(f'{get_time()} {Fore.YELLOW}Loading Frida Java bridge...{Style.RESET_ALL}', flush=True)

		try:
			frida_tools_path = os.path.dirname(frida_tools.__file__)
			java_bridge_path = os.path.join(frida_tools_path, 'bridges', 'java.js')

			with open(java_bridge_path, 'r', encoding='utf-8') as f:
				java_s = f.read()

			java_s += '\n\nObject.defineProperty(globalThis, "Java", { value: bridge });'

			print(f'{get_time()} {Fore.GREEN}Java bridge loaded.{Style.RESET_ALL}', flush=True)
		except Exception as e:
			print(f'{get_time()} {Fore.RED}CRITICAL: Could not load Java bridge: {e}{Style.RESET_ALL}', flush=True)
			print(f'{get_time()} {Fore.RED}Run: pip install frida-tools{Style.RESET_ALL}', flush=True)

			sys.exit(1)

		print(f'{get_time()} {Fore.CYAN}Initializing backend...{Style.RESET_ALL}', flush=True)

		config.backend = Backend()

		print(f'{get_time()} {Fore.GREEN}Tracker+Mastermind backend initialized.{Style.RESET_ALL}', flush=True)

		print(f'{get_time()} {Fore.YELLOW}Loading agent: {config.JS_SCRIPT_PATH}...{Style.RESET_ALL}', flush=True)

		agent_raw = load_script(config.JS_SCRIPT_PATH)
		agent_wrapped = wrap_user_script(config.JS_SCRIPT_PATH, agent_raw)
		mq_wrapper = create_message_queue_wrapper()
		final_code = build_final_script([java_s, mq_wrapper, agent_wrapped])

		print(f'{get_time()} {Fore.GREEN}Agent bundled.{Style.RESET_ALL}', flush=True)
		
		print(f'{get_time()} {Fore.WHITE}Attaching to {config.PACKAGE_NAME}...{Style.RESET_ALL}', flush=True)
		print(f'{get_time()} {Fore.YELLOW}=== PLEASE LAUNCH THE GAME ON YOUR PHONE ==={Style.RESET_ALL}', flush=True)

		config.session = None
		while config.session is None:
			try:
				config.session = device.attach(config.PACKAGE_NAME)
			except frida.ProcessNotFoundError:
				time.sleep(1)
			except Exception as e:
				print(f'{get_time()} {Fore.RED}Connection error: {e}{Style.RESET_ALL}', flush=True)

				time.sleep(1)

		print(f'{get_time()} {Fore.GREEN}Attached!{Style.RESET_ALL}', flush=True)

		config.script = config.session.create_script(final_code)
		config.script.on('message', frida_bridge.on_message)
		config.script.load()

		# Пушим API-ключи в агент. Агент регистрирует RPC асинхронно
		# (через waitForJava → Java.perform), поэтому делаем несколько попыток.
		bot_api_keys = getattr(config.backend.tracker, 'API_KEYS', [])
		if bot_api_keys:
			pushed = False
			for attempt in range(10):
				try:
					config.script.exports_sync.setbotapikey(bot_api_keys[0])
					print(
						f'{get_time()} {Fore.GREEN}Bot API key pushed to agent '
						f'(attempt {attempt + 1}).{Style.RESET_ALL}',
						flush=True
					)
					pushed = True
					break
				except Exception:
					time.sleep(0.3)
			if not pushed:
				print(
					f'{get_time()} {Fore.YELLOW}Warning: could not push Bot API key '
					f'after 10 attempts. Spammer will show API error.{Style.RESET_ALL}',
					flush=True
				)
		else:
			print(
				f'{get_time()} {Fore.YELLOW}No TRACKER_API_KEYS configured — '
				f'Spammer will be unavailable.{Style.RESET_ALL}',
				flush=True
			)

		print(f'{get_time()} {Fore.GREEN}Injection successful. Agent running.{Style.RESET_ALL}', flush=True)
		print(f'{get_time()} {Fore.CYAN}Starting RPC polling thread...{Style.RESET_ALL}', flush=True)

		poller = threading.Thread(
			target=frida_bridge.poll_agent_messages,
			daemon=True,
			name='RPC-Poller'
		)
		poller.start()

		print(f'{get_time()} {Fore.GREEN}[Poller] RPC polling thread started...{Style.RESET_ALL}', flush=True)
		print(f'{get_time()} {Fore.GREEN}--- Script running. Press Enter to exit. ---{Style.RESET_ALL}', flush=True)

		try:
			input()
		except (KeyboardInterrupt, EOFError):
			print(f'\n{get_time()} {Fore.YELLOW}Shutting down...{Style.RESET_ALL}', flush=True)

	except frida.NotSupportedError as e:
		print(f'{get_time()} {Fore.RED}Error: {e}{Style.RESET_ALL}', flush=True)

		sys.exit(1)
	except frida.TimedOutError:
		print(f'{get_time()} {Fore.RED}Error: Device not found.{Style.RESET_ALL}', flush=True)

		sys.exit(1)
	except KeyboardInterrupt:
		print(f'\n{get_time()} {Fore.YELLOW}Interrupted.{Style.RESET_ALL}', flush=True)
	except Exception as e:
		print(f'{get_time()} {Fore.RED}Unexpected error: {e}{Style.RESET_ALL}', flush=True)

		traceback.print_exc()

		sys.exit(1)
	finally:
		config.shutdown_event.set()

		if config.session:
			try:
				config.session.detach()
			except Exception:
				pass

		print(f'{get_time()} {Fore.WHITE}Shutdown complete.{Style.RESET_ALL}', flush=True)
