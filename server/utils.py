import json
import os
import sys
from datetime import datetime
from colorama import Fore, Style

def get_time():
	return f'[{datetime.now().strftime("%H:%M:%S")}]'

def banner(module=None):
	os.system('cls' if os.name == 'nt' else 'clear')

	sep = '=' * 60
	msg  = f'{Style.BRIGHT}{Fore.RED}{sep}{Style.RESET_ALL}\n'
	msg += f'{Style.BRIGHT}{Fore.RED}Men{Fore.YELLOW}tal{Fore.WHITE}ist {Fore.CYAN}Mobile CLI{Style.RESET_ALL}'

	if module:
		msg += f'  {Fore.RED}|{Style.RESET_ALL}  {module}'

	msg += f'\n{Style.BRIGHT}{Fore.MAGENTA}by Corruptor{Style.RESET_ALL}\n'
	msg += f'\n{Style.DIM}{Fore.CYAN}Press Ctrl+C to quit{Style.RESET_ALL}\n'
	msg += f'{Style.BRIGHT}{Fore.RED}{sep}{Style.RESET_ALL}\n'

	print(msg)

def _parse_socketio(text):
	if not isinstance(text, str) or not text.startswith('42'):
		return None, None
	
	i = text.find('[')

	if i < 0:
		return None, None

	try:
		arr = json.loads(text[i:])
		evt = arr[0]
		raw = arr[1] if len(arr) > 1 else None

		if isinstance(raw, str):
			try:
				raw = json.loads(raw)
			except Exception:
				pass

		return evt, raw
	except Exception:
		return None, None

def load_script(path):
	try:
		with open(path, 'r', encoding='utf-8') as f:
			return f.read()
	except FileNotFoundError:
		print(f'{get_time()} {Fore.RED}Script not found: {path}{Style.RESET_ALL}', flush=True)

		sys.exit(1)
	except Exception as e:
		print(f'{get_time()} {Fore.RED}Error loading script: {e}{Style.RESET_ALL}', flush=True)

		sys.exit(1)

def wrap_user_script(name, script):
	# agent.js всегда plain JS (собирается через js/build.js, не frida-compile).
	# Оборачиваем через Script.evaluate — так агент получает тот же контекст
	# что и остальные фрагменты финального скрипта.
	return f'Script.evaluate({json.dumps(name)}, {json.dumps(script)});'


def build_final_script(raw_fragments):
	fragments = []
	next_id = 1

	for raw in raw_fragments:
		if raw.startswith('📦\n'):
			fragments.append(raw[2:])

		else:
			size = len(raw.encode('utf-8'))
			fragments.append(f'{size} /frida/repl-{next_id}.js\n✄\n{raw}')
			next_id += 1

	return '📦\n' + '\n✄\n'.join(fragments)

def create_message_queue_wrapper():
	return '''
// === Message Queue Infrastructure ===
globalThis._mq = [];

rpc.exports.getqueuedmessages = function() {
	const result = JSON.stringify(globalThis._mq);
	globalThis._mq = [];
	return result;
};

send({ type: 'log', message: '🟢 [WRAPPER] Message queue initialized' });
'''
