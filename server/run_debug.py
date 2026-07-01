"""
run_debug.py — режим Debug (ADB).

Работает как раньше: подключается к телефону по USB/ADB,
инжектирует agent.js через Frida, общается через RPC.

Используй для разработки и тестирования.
Для production используй server.py.
"""

import frida
import frida_tools
import threading
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from colorama import Fore, Style, init

# server/ — сосед mentalist_server/
_SERVER_DIR = Path(__file__).parent.parent / 'server'
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

# mentalist_server/ — для debug_bridge
_SELF_DIR = Path(__file__).parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

import config
from utils import get_time, banner, load_script, wrap_user_script, build_final_script, create_message_queue_wrapper
from backend import Backend
from debug_bridge import DebugBridge

init(autoreset=True)


def main():
    try:
        banner()

        # ── Подключение к устройству ───────────────────────────────────────────
        print(f'{get_time()} {Fore.WHITE}Waiting for device connection...{Style.RESET_ALL}', flush=True)

        device_serial = os.environ.get('DEVICE_SERIAL') or config.DEVICE_SERIAL

        if device_serial:
            try:
                device = frida.get_device(device_serial)
            except Exception:
                print(f'{get_time()} {Fore.YELLOW}Serial failed, trying USB...{Style.RESET_ALL}', flush=True)
                device = frida.get_usb_device(timeout=10)
        else:
            try:
                device = frida.get_usb_device(timeout=10)
            except Exception:
                devices = frida.enumerate_devices()
                if devices:
                    device = devices[0]
                else:
                    raise Exception('No devices found')

        print(f'{get_time()} {Fore.GREEN}Device connected: {device.name}{Style.RESET_ALL}', flush=True)

        # ── Java bridge ───────────────────────────────────────────────────────
        print(f'{get_time()} {Fore.YELLOW}Loading Frida Java bridge...{Style.RESET_ALL}', flush=True)
        try:
            frida_tools_path = os.path.dirname(frida_tools.__file__)
            java_bridge_path = os.path.join(frida_tools_path, 'bridges', 'java.js')
            with open(java_bridge_path, 'r', encoding='utf-8') as f:
                java_s = f.read()
            java_s += '\n\nObject.defineProperty(globalThis, "Java", { value: bridge });'
            print(f'{get_time()} {Fore.GREEN}Java bridge loaded.{Style.RESET_ALL}', flush=True)
        except Exception as e:
            print(f'{get_time()} {Fore.RED}CRITICAL: Java bridge failed: {e}{Style.RESET_ALL}', flush=True)
            sys.exit(1)

        # ── Backend ───────────────────────────────────────────────────────────
        print(f'{get_time()} {Fore.CYAN}Initializing backend...{Style.RESET_ALL}', flush=True)
        backend = Backend()
        print(f'{get_time()} {Fore.GREEN}Backend initialized.{Style.RESET_ALL}', flush=True)

        # ── Загрузка агента ───────────────────────────────────────────────────
        agent_path = os.environ.get('AGENT_JS_PATH') or config.JS_SCRIPT_PATH
        print(f'{get_time()} {Fore.YELLOW}Loading agent: {agent_path}...{Style.RESET_ALL}', flush=True)

        agent_raw     = load_script(agent_path)
        agent_wrapped = wrap_user_script(agent_path, agent_raw)
        mq_wrapper    = create_message_queue_wrapper()
        final_code    = build_final_script([java_s, mq_wrapper, agent_wrapped])

        print(f'{get_time()} {Fore.GREEN}Agent bundled.{Style.RESET_ALL}', flush=True)

        # ── Attach ────────────────────────────────────────────────────────────
        package = os.environ.get('PACKAGE_NAME') or config.PACKAGE_NAME
        print(f'{get_time()} {Fore.WHITE}Attaching to {package}...{Style.RESET_ALL}', flush=True)
        print(f'{get_time()} {Fore.YELLOW}=== PLEASE LAUNCH THE GAME ON YOUR PHONE ==={Style.RESET_ALL}', flush=True)

        session = None
        while session is None:
            try:
                session = device.attach(package)
            except frida.ProcessNotFoundError:
                time.sleep(1)
            except Exception as e:
                print(f'{get_time()} {Fore.RED}Connection error: {e}{Style.RESET_ALL}', flush=True)
                time.sleep(1)

        print(f'{get_time()} {Fore.GREEN}Attached!{Style.RESET_ALL}', flush=True)

        # ── Bridge (обработчик сообщений) ─────────────────────────────────────
        bridge = DebugBridge(backend=backend, session_ref=[session])

        script = session.create_script(final_code)
        script.on('message', bridge.on_message)
        script.load()

        # ── Bot API key ───────────────────────────────────────────────────────
        bot_api_keys = getattr(backend.tracker, 'API_KEYS', [])
        if bot_api_keys:
            pushed = False
            for attempt in range(10):
                try:
                    script.exports_sync.setbotapikey(bot_api_keys[0])
                    print(f'{get_time()} {Fore.GREEN}Bot API key pushed (attempt {attempt + 1}).{Style.RESET_ALL}', flush=True)
                    pushed = True
                    break
                except Exception:
                    time.sleep(0.3)
            if not pushed:
                print(f'{get_time()} {Fore.YELLOW}Warning: could not push Bot API key.{Style.RESET_ALL}', flush=True)

        bridge.script = script

        print(f'{get_time()} {Fore.GREEN}Injection successful. Agent running.{Style.RESET_ALL}', flush=True)

        # ── Polling thread ────────────────────────────────────────────────────
        shutdown_event = threading.Event()

        def poll():
            print(f'{get_time()} {Fore.CYAN}[Poller] RPC polling thread started...{Style.RESET_ALL}', flush=True)
            time.sleep(0.5)
            while not shutdown_event.is_set():
                try:
                    messages_json = script.exports_sync.getqueuedmessages()
                    if messages_json:
                        import json
                        for msg_str in json.loads(messages_json):
                            try:
                                bridge.on_message({'type': 'send', 'payload': json.loads(msg_str)}, None)
                            except Exception as e:
                                print(f'{get_time()} {Fore.RED}[Poller Inner] {e}{Style.RESET_ALL}', flush=True)
                except Exception as e:
                    err = str(e).lower()
                    if 'destroyed' in err or 'detached' in err:
                        print(f'\n{get_time()} {Fore.RED}[Poller] Connection lost.{Style.RESET_ALL}', flush=True)
                        shutdown_event.set()
                        break
                    elif 'method not found' not in err and 'getqueuedmessages' not in err:
                        print(f'{get_time()} {Fore.RED}[Poller] {e}{Style.RESET_ALL}', flush=True)
                shutdown_event.wait(0.1)
            print(f'{get_time()} {Fore.CYAN}[Poller] Stopped.{Style.RESET_ALL}', flush=True)

        poller = threading.Thread(target=poll, daemon=True, name='RPC-Poller')
        poller.start()

        print(f'{get_time()} {Fore.GREEN}[Poller] RPC polling thread started...{Style.RESET_ALL}', flush=True)
        print(f'{get_time()} {Fore.GREEN}--- Script running. Press Enter to exit. ---{Style.RESET_ALL}', flush=True)

        try:
            input()
        except (KeyboardInterrupt, EOFError):
            print(f'\n{get_time()} {Fore.YELLOW}Shutting down...{Style.RESET_ALL}', flush=True)

    except KeyboardInterrupt:
        print(f'\n{get_time()} {Fore.YELLOW}Interrupted.{Style.RESET_ALL}', flush=True)
    except Exception as e:
        print(f'{get_time()} {Fore.RED}Unexpected error: {e}{Style.RESET_ALL}', flush=True)
        traceback.print_exc()
    finally:
        try:
            session.detach()
        except Exception:
            pass
        print(f'{get_time()} {Fore.WHITE}Shutdown complete.{Style.RESET_ALL}', flush=True)


if __name__ == '__main__':
    main()
