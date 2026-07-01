import requests
import threading
import hashlib
import json
import re
import os
import sys
import time
import random
import traceback
from copy import deepcopy
from pathlib import Path
from colorama import Back, Fore, Style
from dotenv import dotenv_values
import config
from analytics import BayesEngine, NLPAnalyzer
from utils import _parse_socketio, get_time, banner

class _FakeEel:
	def __getattr__(self, name):
		def _noop(*a, **kw): return lambda *a2, **kw2: None

		return _noop

eel = _FakeEel()

def sync_playwright():
	class _ctx:
		def __enter__(self):
			return self
		def __exit__(self, *a):
			pass

	return _ctx()

class PlaywrightTimeoutError(Exception):
	pass

class MentalistUpdater:
	def __init__(self, **kw):
		pass


	def interactive_update(self):
		pass


MENTALIST_DATA_DIR = Path(os.environ.get('MENTALIST_DATA_DIR', 'data'))
USER_DATA_DIR = Path(os.environ.get('USER_DATA_DIR', 'user_data'))
CONFIG_PATH = os.environ.get('CONFIG_PATH') or str(Path(__file__).parent.parent / 'config.txt')
VERSION = os.environ.get('VERSION', '1.0.0')
_launch_mode = 'CLI'


def _pause(msg=''):
	print(msg, flush=True)
	input()

def get_resource_path(p):
	return Path(p)

def find_chrome_executable():
	return

def generate_random_user_agent(**kw):
	return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'


MACOS_DISABLE_PLAYWRIGHT_THREADING = False


class Tracker:
	def __init__(self):
		self.config = dotenv_values(CONFIG_PATH)

		try:
			self.API_KEYS = self.config['TRACKER_API_KEYS'].split(',')
		except KeyError:
			print(
				f'{Style.BRIGHT}{Back.RED}API key(s) not found!{Back.RESET}', flush=True
			)

			sys.exit(1)

		self._api_gen = self.switch_api_key()

		self.SERVER_ENABLED = self.config.get('SYNC_SERVER_ENABLED', 'false').lower() == 'true'
		self.SERVER_URL = self.config.get('SYNC_SERVER_URL', 'http://localhost:1101')
		self.SERVER_API_KEY = self.config.get('SYNC_SERVER_API_KEY', '')
		self.SERVER_TIMEOUT = 10

		self.data_hashes = {
			'cards': None,
			'icons': None,
			'role_profiles': None
		}

		self.BOT_BASE_URL = 'https://api.wolvesville.com/'
		self.BEARER_BASE_URL = 'https://core.api-wolvesville.com/'
		self.BEARER_TOKEN = None
		self.CF_JWT = None
		self.BEARER_HEADERS = {}
		self._lock = threading.RLock()
		self.ROTATION = []
		self.PLAYERS = []
		self.ROLES = {}
		self.ADVANCED_ROLES = {}
		self.RANDOM_ROLE_TYPES = {
			'random-villager-normal': [
				'aura-seer',
				'beast-hunter',
				'bodyguard',
				'doctor',
				'flower-child',
				'loudmouth',
				'mayor',
				'priest',
				'red-lady',
				'sheriff',
				'witch'
			],
			'random-villager-strong': [
				'detective',
				'jailer',
				'medium',
				'seer',
				'vigilante'
			],
			'random-villager-support': [
				'doctor',
				'bodyguard',
				'ghost-lady',
				'sheriff',
				'beast-hunter',
				'bellringer'
			],
			'random-werewolf': 'WEREWOLF',
			'random-werewolf-weak': 'WEREWOLF',
			'random-werewolf-strong': 'WEREWOLF',
			'random-support-werewolf': [
				'nightmare-werewolf',
				'wolf-shaman',
				'toxic-wolf'
			],
			'random-killer': ['arsonist', 'bandit', 'corruptor', 'serial-killer'],
			'random-voting': ['fool'],
			'random-other': ['cupid', 'cursed']
		}
		self.ROTATION_ICONS = {}
		self.PLAYER_CARDS = {}
		self.ICONS = {}
		self.THREAT_LEVELS = {}
		self.PLAYER_CLAIMS = {}
		self.PLAYER_ALLIANCES = {}
		self.mastermind = None
		self.PREV_PLAYERS = []
		self.game_status = 'unknown'
		self.day = 0
		self.phase = ''
		self.my_role = ''
		self.roles_in_rotation = []
		self.id_by_num = {}
		self.num_by_id = {}
		self.role_icons_map = {}
		self.reset()
		self.load_cards()
		self.load_icons()
		self.get_roles()
		self.ICONS = self.get_icons()
		self.bayes = BayesEngine(self)
		self.nlp = NLPAnalyzer()

		print(
			f'{get_time()} {Fore.CYAN}[Config] TRACKER_API_KEYS count={len(self.API_KEYS)}{Style.RESET_ALL}',
			flush=True
		)

	def reset(self):
		self.PLAYERS = []

		for _ in range(16):
			self.PLAYERS.append(
				{
					'name': None,
					'level': -1,
					'min_level': -1,
					'role': None,
					'team': None,
					'teams_exclude': set(),
					'aura': None,
					'dead': False,
					'equal': set(),
					'not_equal': set(),
					'hero': False,
					'messages': [],
					'mentions': []
				}
			)

		self.id_by_num = {}
		self.num_by_id = {}
		self.role_icons_map = {}
		self.game_status = 'unknown'
		self.day = 0
		self.phase = ''
		self.my_role = ''
		self.roles_in_rotation = []
		self.PLAYER_CLAIMS = {}
		self.PLAYER_ALLIANCES = {}

	@staticmethod
	def predict_player_level(
		received_roses, sent_roses, win_count, lose_count, clan_xp
	):
		min_levels = [
			(clan_xp // 2000) if clan_xp != -1 else 1,
			(received_roses + sent_roses) // 20 or 1,
		]

		return max(min_levels)

	def switch_api_key(self):
		while True:
			for key in self.API_KEYS:
				yield key

	def calculate_hash(self, data):
		json_str = json.dumps(data, sort_keys=True)

		return hashlib.sha256(json_str.encode()).hexdigest()
	
	def sync_with_server(self, data_type, local_data, bidirectional=True):
		if not self.SERVER_ENABLED:
			return False, local_data
		
		try:
			current_hash = self.calculate_hash(local_data)
			
			if self.data_hashes.get(data_type) == current_hash:
				return True, local_data
			
			headers = {
				'X-API-Key': self.SERVER_API_KEY,
				'Content-Type': 'application/json'
			}
			
			if bidirectional:
				endpoint = f'{self.SERVER_URL}/sync/{data_type}'
				payload = {
					'data': local_data,
					'hash': current_hash
				}
				
				response = requests.post(
					endpoint,
					json=payload,
					headers=headers,
					timeout=self.SERVER_TIMEOUT,
					verify=False
				)

			else:
				endpoint = f'{self.SERVER_URL}/get/{data_type}'
				response = requests.get(
					endpoint,
					headers=headers,
					timeout=self.SERVER_TIMEOUT,
					verify=False
				)
			
			if response.status_code == 200:
				result = response.json()
				
				if result.get('status') == 'no_changes':
					self.data_hashes[data_type] = current_hash

					return True, local_data
				
				elif result.get('status') in ['synced', 'success']:
					server_data = result.get('data', {})
					server_hash = result.get('hash', '')
					
					self.data_hashes[data_type] = server_hash
					
					if bidirectional and result.get('server_updated'):
						print(f'{Style.BRIGHT}{Fore.GREEN}Mentalist Server updated with your {data_type}!')
					
					if server_hash != current_hash:
						print(f'{Style.BRIGHT}{Fore.CYAN}Received updates for {data_type} from Mentalist Server.')
						
						return True, server_data
					
					return True, local_data
			
			elif response.status_code == 401:
				print(f'{Style.BRIGHT}{Back.RED}Mentalist Server sync failed: Invalid API key{Back.RESET}')

				return False, local_data
			
			else:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Server sync warning: {response.status_code}')

				return False, local_data
		
		except requests.exceptions.ConnectionError:
			if not hasattr(self, '_server_warning_shown'):
				print(f'{Style.BRIGHT}{Fore.YELLOW}Warning: Cannot connect to Mentalist Server. Using local data.{Fore.RESET}')

				self._server_warning_shown = True

			return False, local_data
		except requests.exceptions.Timeout:
			print(f'{Style.BRIGHT}{Fore.YELLOW}Mentalist Server sync timeout. Using local data.{Fore.RESET}')

			return False, local_data
		except Exception as e:
			print(f'{Style.BRIGHT}{Fore.RED}Mentalist Server sync error: {e}{Fore.RESET}')

			return False, local_data

	@property
	def bot_headers(self):
		api_key = next(self._api_gen)

		return {
			'Authorization': f'Bot {api_key}',
			'Accept': 'application/json',
			'Content-Type': 'application/json'
		}

	def set_auth(self, bearer, cf_jwt):
		with self._lock:
			changed = False

			if bearer and bearer != self.BEARER_TOKEN:
				self.BEARER_TOKEN = bearer
				self.BEARER_HEADERS['Authorization'] = f'Bearer {bearer}'

				print(
					f'{get_time()} {Fore.GREEN}[Auth] ✓ Bearer Token captured: ***{bearer[-12:]}{Style.RESET_ALL}',
					flush=True
				)

				changed = True

			if cf_jwt and cf_jwt != self.CF_JWT:
				self.CF_JWT = cf_jwt
				self.BEARER_HEADERS['Cf-Jwt'] = cf_jwt

				print(
					f'{get_time()} {Fore.GREEN}[Auth] ✓ CF-JWT Token captured: {cf_jwt[:30]}...{Style.RESET_ALL}',
					flush=True
				)

				changed = True

			if changed:
				self.BEARER_HEADERS['Ids'] = '1'

				print(
					f'{get_time()} {Fore.YELLOW}[Auth] Current state: Bearer={bool(self.BEARER_TOKEN)}, CF-JWT={bool(self.CF_JWT)}{Style.RESET_ALL}',
					flush=True
				)

	def _parse_socketio_envelope(self, text):
		if not isinstance(text, str) or not text.startswith('42'):
			return

		i = text.find('[')

		if i < 0:
			return

		try:
			arr = json.loads(text[i:])
			evt = arr[0]
			raw = arr[1] if len(arr) > 1 else None

			if isinstance(raw, str):
				try:
					raw = json.loads(raw)
				except Exception:
					pass

			return (evt, raw)
		except Exception:
			return

	def process_ws(self, direction, text):
		if direction != 'INBOUND':
			return

		evt, payload = _parse_socketio(text)

		if not evt:
			return

		self._on_inbound(evt, payload)

	def _upsert_player_ws(self, p_data):
		if not p_data or 'id' not in p_data:
			return

		pid = p_data['id']
		grid_idx = p_data.get('gridIdx', -1)
		num = grid_idx + 1 if grid_idx >= 0 else None

		if num and 1 <= num <= 16:
			self.id_by_num[num] = pid
			self.num_by_id[pid] = num

			player_idx = num - 1
			username = p_data.get('username')

			if username:
				current_name = self.PLAYERS[player_idx].get('name')

				self.PLAYERS[player_idx]['name'] = username

				level = self.PLAYERS[player_idx].get('level', -1)

				if level < 0:
					print(
						f'{get_time()} {Fore.CYAN}[Profiles] Triggering fetch for {username} (slot {num}){Style.RESET_ALL}',
						flush=True
					)

					self._spawn_profile_fetch(username)

			if 'isAlive' in p_data:
				self.PLAYERS[player_idx]['dead'] = not p_data['isAlive']

			if 'roleRevealed' in p_data or 'roleId' in p_data:
				role_id = p_data.get('roleRevealed') or p_data.get('roleId')

				if role_id:
					self._set_role_by_id(player_idx, role_id)

	def _on_inbound(self, evt, payload):
		if evt == 'game-joined':
			print(f'{get_time()} {Fore.YELLOW}[Game] New game joined. Resetting state...{Style.RESET_ALL}', flush=True)
			
			self.reset()

			# banner() убран — он очищал консоль и удалял все предыдущие логи

			return

		if evt in (
			'game-set-game-status',
			'game-reconnect-set-game-status',
		) and isinstance(payload, dict):
			self.game_status = payload.get('gameStatus', self.game_status)

			if 'day' in payload:
				self.day = payload['day']

			return

		if evt == 'game-settings-changed' and isinstance(payload, dict):
			roles = payload.get('roles')

			if isinstance(roles, list):
				self.roles_in_rotation = roles
				self._update_rotation_from_ws()

			return

		if evt == 'players-and-equipped-items' and isinstance(payload, dict):
			for p in payload.get('players', []) or []:
				self._upsert_player_ws(p)

			return

		if evt == 'player-joined-and-equipped-items' and isinstance(payload, dict):
			if 'player' in payload:
				self._upsert_player_ws(payload['player'])

			return

		if evt == 'player-grid-idx' and isinstance(payload, dict):
			pid = payload.get('playerId')

			if pid is not None and 'gridIdx' in payload:
				self._upsert_player_ws({'id': pid, 'gridIdx': payload['gridIdx']})

			return

		if evt == 'player-disconnected' and isinstance(payload, dict):
			pid = payload.get('id')

			if pid:
				self._upsert_player_ws(
					{'id': pid, 'isAlive': payload.get('isAlive', True)}
				)

			return

		if evt == 'game-started' and isinstance(payload, dict):
			self.my_role = payload.get('role', self.my_role)
			self.game_status = 'started'

			for p in payload.get('players', []) or []:
				self._upsert_player_ws(p)

			if self.mastermind:
				self.mastermind.update_state()

			return

		if evt == 'game-night-started' and isinstance(payload, dict):
			if 'day' in payload:
				self.day = payload['day']

			self.phase = 'night'

			return

		if evt == 'game-day-started' and isinstance(payload, dict):
			if 'day' in payload:
				self.day = payload['day']

			self.phase = 'day'

			return

		if evt == 'game-day-voting-started' and isinstance(payload, dict):
			if 'day' in payload:
				self.day = payload['day']

			self.phase = 'day-voting'

			return

		if evt == 'game-phase-transition-active' and isinstance(payload, dict):
			if 'day' in payload:
				self.day = payload['day']

			if 'phase' in payload:
				self.phase = payload['phase']

			return

		if evt == 'game-set-role-icons' and isinstance(payload, dict):
			m = payload.get('roleToRoleIconIdMap')

			if isinstance(m, dict):
				self.role_icons_map.update(m)

			return

		if evt == 'game-werewolves-set-roles' and isinstance(payload, dict):
			ww_roles = payload.get('werewolves')

			if isinstance(ww_roles, dict):
				for pid, role_id in ww_roles.items():
					if pid and role_id:
						num = self.num_by_id.get(pid)

						if num and 1 <= num <= 16:
							player_idx = num - 1

							self._set_role_by_id(player_idx, role_id)

		if evt == 'game-role-revealed' and isinstance(payload, dict):
			pid = payload.get('playerId')
			role_id = payload.get('roleId')

			if pid and role_id:
				num = self.num_by_id.get(pid)

				if num and 1 <= num <= 16:
					player_idx = num - 1

					self._set_role_by_id(player_idx, role_id)

			return

		if evt == 'game-players-killed' and isinstance(payload, dict):
			for v in payload.get('victims', []) or []:
				pid = v.get('targetPlayerId')

				if pid:
					num = self.num_by_id.get(pid)

					if num and 1 <= num <= 16:
						player_idx = num - 1

						self.PLAYERS[player_idx]['dead'] = True

						role_id = v.get('targetPlayerRole')

						if role_id:
							self._set_role_by_id(player_idx, role_id)

			if self.mastermind:
				self.mastermind.update_state()

			self.calculate_threats()

			return

		if evt == 'game-day-vote-set' and isinstance(payload, dict):
			return

		if evt == 'game:chat-public:msg' and isinstance(payload, dict):
			author_id = payload.get('authorId', 'system')
			msg_text = payload.get('msg', '')
			num = self.num_by_id.get(author_id)

			if num and 1 <= num <= 16:
				self.PLAYERS[num - 1]['messages'].append(msg_text)

				for prev in self.PREV_PLAYERS:
					if num - 1 < len(prev):
						prev[num - 1]['messages'].append(msg_text)

				number_str = ''

				for s in msg_text:
					if s.isdigit():
						number_str += s

					elif number_str:
						if int(number_str) in range(1, 17):
							target_idx = int(number_str) - 1

							self.PLAYERS[target_idx]['mentions'].append(msg_text)

							for prev in self.PREV_PLAYERS:
								if target_idx < len(prev):
									prev[target_idx]['mentions'].append(msg_text)

						number_str = ''

			if self.mastermind:
				self.mastermind.update_state()

			self.parse_chat_messages([])
			self.calculate_threats()

			return

	def _update_rotation_from_ws(self):
		if not self.roles_in_rotation or not self.ROLES:
			return

		rotation = []

		for rid in self.roles_in_rotation:
			role_info = self.ROLES.get(rid)

			if role_info:
				r = role_info.copy()
				r['id'] = rid
				rotation.append(r)

		self.ROTATION = rotation

	def _set_role_by_id(self, player_idx, role_id):
		if not 0 <= player_idx < 16:
			return

		self.PLAYERS[player_idx]['role'] = role_id

		role_info = self.ROLES.get(role_id)

		if role_info:
			self.PLAYERS[player_idx]['team'] = role_info.get('team')
			self.PLAYERS[player_idx]['aura'] = role_info.get('aura')

		name = self.PLAYERS[player_idx].get('name')

		if name and role_id in self.role_icons_map:
			self.write_icons(name, {role_id: self.role_icons_map[role_id]})

	def bearer_headers(self):
		headers = {'Ids': '1'}

		if self.BEARER_TOKEN:
			headers['Authorization'] = f'Bearer {self.BEARER_TOKEN}'

		if self.CF_JWT:
			headers['Cf-Jwt'] = self.CF_JWT

		return headers

	def get_roles(self):
		try:
			print(
				f'{get_time()} {Fore.YELLOW}[API] GET roles...{Style.RESET_ALL}',
				flush=True
			)

			if not self.API_KEYS:
				print(
					f'{get_time()} {Fore.YELLOW}[API] No TRACKER_API_KEYS provided; skipping roles fetch{Style.RESET_ALL}',
					flush=True
				)

				return

			r = requests.get(
				self.BOT_BASE_URL + 'roles',
				headers=self.bot_headers,
				timeout=10,
				verify=False
			)

			if not r.ok:
				print(
					f'{get_time()} {Fore.RED}[API] roles failed: {r.status_code}{Style.RESET_ALL}',
					flush=True
				)

				return

			data = r.json()
			roles = {}

			for role in data.get('roles', []):
				rid = role['id'].replace('random-village', 'random-villager')
				name = role.get('name')

				if rid == 'random-villager-normal':
					name = 'RRV'

				elif rid == 'random-villager-strong':
					name = 'RSV'

				elif rid == 'random-werewolf':
					name = 'RW'

				elif rid == 'random-killer':
					name = 'RK'

				elif rid == 'random-voting':
					name = 'RV'

				team = role.get('team')

				if team in ['VILLAGER', 'RANDOM_VILLAGER']:
					team = 'VILLAGER'

				elif team in ['WEREWOLF', 'RANDOM_WEREWOLF']:
					team = 'WEREWOLF'

				else:
					team = 'SOLO'

				roles[rid] = {'name': name, 'team': team, 'aura': role.get('aura')}

			roles['cursed'] = roles.pop(
				'cursed-human',
				roles.get(
					'cursed', {'name': 'cursed', 'team': 'VILLAGER', 'aura': 'GOOD'}
				),
			)

			roles['red-lady'] = roles.pop(
				'harlot',
				roles.get(
					'red-lady', {'name': 'red-lady', 'team': 'VILLAGER', 'aura': 'GOOD'}
				),
			)

			self.ROLES = roles

			adv = data.get('advancedRolesMapping', {})

			if 'cursed-human' in adv:
				adv['cursed'] = adv.pop('cursed-human')

			if 'harlot' in adv:
				adv['red-lady'] = adv.pop('harlot')

			self.ADVANCED_ROLES = adv

			print(
				f'{get_time()} {Fore.GREEN}[API] roles OK: {len(self.ROLES)} base roles{Style.RESET_ALL}',
				flush=True
			)
		except Exception as e:
			print(
				f'{get_time()} {Fore.RED}[API] roles exception: {e}{Style.RESET_ALL}',
				flush=True
			)

			traceback.print_exc()

	def get_icons(self):
		try:
			print(
				f'{get_time()} {Fore.YELLOW}[API] GET roleIcons...{Style.RESET_ALL}',
				flush=True
			)

			if not self.API_KEYS:
				print(
					f'{get_time()} {Fore.YELLOW}[API] No TRACKER_API_KEYS provided; skipping roleIcons fetch{Style.RESET_ALL}',
					flush=True
				)

				return {}

			r = requests.get(
				self.BOT_BASE_URL + 'items/roleIcons',
				headers=self.bot_headers,
				timeout=10,
				verify=False,
			)

			if not r.ok:
				print(
					f'{get_time()} {Fore.RED}[API] roleIcons failed: {r.status_code}{Style.RESET_ALL}',
					flush=True
				)

				return {}

			data = r.json()
			icons = {}

			for icon in data:
				icons[icon['id']] = {
					'filename': icon['image']['url'].split('roleIcons/')[1],
					'role': icon['roleId']
				}

			print(
				f'{get_time()} {Fore.GREEN}[API] roleIcons OK: {len(icons)} items{Style.RESET_ALL}',
				flush=True
			)

			return icons
		except Exception as e:
			print(
				f'{get_time()} {Fore.RED}[API] roleIcons exception: {e}{Style.RESET_ALL}',
				flush=True
			)

			traceback.print_exc()

			return {}

	def load_cards(self):
		try:
			with open('.mentalist_data/cards.json', 'r', encoding='utf-8') as f:
				local_cards = json.load(f)

			print(
				f'{get_time()} {Fore.GREEN}[Storage] cards.json loaded ({len(local_cards)} players){Style.RESET_ALL}',
				flush=True
			)
		except:
			local_cards = {}

			print(
				f'{get_time()} {Fore.YELLOW}[Storage] cards.json not found, starting empty{Style.RESET_ALL}',
				flush=True
			)

		success, self.PLAYER_CARDS = self.sync_with_server('cards', local_cards, bidirectional=True)
		
		if success and self.PLAYER_CARDS != local_cards:
			self.save_cards()

		elif not success:
			 self.PLAYER_CARDS = local_cards

	def write_cards(self, player, cards):
		if player not in self.PLAYER_CARDS:
			self.PLAYER_CARDS[player] = cards

		else:
			for src_role, dst_role in cards.items():
				if type(dst_role) == str:
					dst_role = [dst_role]

				if src_role not in self.PLAYER_CARDS[player]:
					self.PLAYER_CARDS[player][src_role] = dst_role

				else:
					for role in dst_role:
						if role not in self.PLAYER_CARDS[player][src_role]:
							self.PLAYER_CARDS[player][src_role].append(role)

	def save_cards(self):
		if not os.path.isdir('.mentalist_data'):
			os.mkdir('.mentalist_data')

		with open('.mentalist_data/cards.json', 'w', encoding='utf-8') as f:
			json.dump(self.PLAYER_CARDS, f, ensure_ascii=False)
		
		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('cards', self.PLAYER_CARDS, True),
				daemon=True
			).start()

	def load_icons(self):
		try:
			with open('.mentalist_data/icons.json', 'r', encoding='utf-8') as f:
				local_icons = json.load(f)

			print(
				f'{get_time()} {Fore.GREEN}[Storage] icons.json loaded ({len(local_icons)} players){Style.RESET_ALL}',
				flush=True
			)
		except:
			local_icons = {}

			print(
				f'{get_time()} {Fore.YELLOW}[Storage] icons.json not found, starting empty{Style.RESET_ALL}',
				flush=True
			)

		success, self.PLAYER_ICONS = self.sync_with_server('icons', local_icons, bidirectional=True)
		
		if success and self.PLAYER_ICONS != local_icons:
			self.save_icons()

		elif not success:
			 self.PLAYER_ICONS = local_icons

	def write_icons(self, player, icons):
		if player not in self.PLAYER_ICONS:
			self.PLAYER_ICONS[player] = icons

		else:
			self.PLAYER_ICONS[player].update(icons)

	def save_icons(self):
		if not os.path.isdir('.mentalist_data'):
			os.mkdir('.mentalist_data')

		with open('.mentalist_data/icons.json', 'w', encoding='utf-8') as f:
			json.dump(self.PLAYER_ICONS, f, ensure_ascii=False)

		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('icons', self.PLAYER_ICONS, True),
				daemon=True
			).start()

	def get_player(self, username):
		ENDPOINT = f'players/search?username={username}'

		try:
			data = requests.get(
				f'{self.BOT_BASE_URL}{ENDPOINT}',
				headers=self.bot_headers,
				verify=False,
				timeout=10
			)

			if not data.ok:
				print(
					f'{get_time()} {Fore.RED}[API] get_player failed for {username}: {data.status_code} - {data.text[:100]}{Style.RESET_ALL}',
					flush=True
				)

				return data.status_code, data.text

			data = data.json()
		except Exception as e:
			print(
				f'{get_time()} {Fore.RED}[API] get_player exception for {username}: {e}{Style.RESET_ALL}',
				flush=True
			)

			return 500, str(e)

		game_stats = data.get('gameStats', {})
		player_id = data['id']
		level = data.get('level', -1)
		received_roses = data.get('receivedRosesCount', -1)
		sent_roses = data.get('sentRosesCount', -1)
		win_count = game_stats.get('totalWinCount', -1)
		lose_count = game_stats.get('totalLoseCount', -1)
		clan_id = data.get('clanId')
		clan_xp = self.get_player_clan_xp(clan_id, player_id)
		min_level = (
			self.predict_player_level(
				received_roses, sent_roses, win_count, lose_count, clan_xp
			)
			if level == -1
			else level
		)

		cards = {}

		for card in data['roleCards']:
			if card['rarity'] == 'COMMON':
				continue

			if card['roleIdBase'] == 'harlot':
				card['roleIdBase'] = 'red-lady'

			elif card['roleIdBase'] == 'cursed-human':
				card['roleIdBase'] = 'cursed'

			elif card['roleIdBase'] in ['fool', 'headhunter']:
				continue

			if 'roleIdsAdvanced' in card:
				for i in range(len(card['roleIdsAdvanced'])):
					if card['roleIdsAdvanced'][i] == 'harlot':
						card['roleIdsAdvanced'][i] = 'red-lady'

					elif card['roleIdsAdvanced'][i] == 'cursed-human':
						card['roleIdsAdvanced'][i] = 'cursed'

				cards[card['roleIdBase']] = card['roleIdsAdvanced']

		time.sleep(0.1)

		icons = {}

		if self.BEARER_TOKEN:
			try:
				ENDPOINT = f'playerRoleStats/achievements/{player_id}'
				data2 = requests.get(
					f'{self.BEARER_BASE_URL}{ENDPOINT}',
					headers=self.bearer_headers(),
					verify=False,
					timeout=10
				)

				if data2.ok:
					achievements = data2.json()

					for achievement in achievements:
						if achievement['roleId'] == 'harlot':
							achievement['roleId'] = 'red-lady'

						elif achievement['roleId'] == 'cursed-human':
							achievement['roleId'] = 'cursed'

						if 'roleIconId' in achievement:
							icons[achievement['roleId']] = achievement['roleIconId']

						if achievement['roleId'] in ['fool', 'headhunter', 'zombie']:
							continue

						for role in self.ROLES:
							if achievement['roleId'] in self.ADVANCED_ROLES.get(
								role, []
							):
								if role not in cards:
									cards[role] = [achievement['roleId']]

								break

				else:
					print(
						f'{get_time()} {Fore.YELLOW}[API] achievements failed for {username}: {data2.status_code}{Style.RESET_ALL}',
						flush=True
					)
			except Exception as e:
				print(
					f'{get_time()} {Fore.YELLOW}[API] achievements exception for {username}: {e}{Style.RESET_ALL}',
					flush=True
				)

		return 0, level, min_level, cards, icons

	def get_player_clan_xp(self, clan_id, player_id):
		if not clan_id:
			return -1

		ENDPOINT = f'clans/{clan_id}/members'
		data = requests.get(
			f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False
		)

		if not data.ok:
			return -1

		data = data.json()

		for player in data:
			if player_id == player.get('playerId'):
				return player.get('xp')

		return -1

	def _spawn_profile_fetch(self, username):
		if not username:
			return

		if not hasattr(self, '_fetching_users'):
			self._fetching_users = set()

		if username in self._fetching_users:
			print(
				f'{get_time()} {Fore.YELLOW}[Profiles] Already fetching {username}, skipping{Style.RESET_ALL}',
				flush=True
			)

			return

		self._fetching_users.add(username)

		print(
			f'{get_time()} {Fore.GREEN}[Profiles] Starting fetch for {username}{Style.RESET_ALL}',
			flush=True
		)

		def _job():
			try:
				print(
					f'{get_time()} {Fore.CYAN}[Profiles] Fetching data for {username}...{Style.RESET_ALL}',
					flush=True
				)

				data = self.get_player(username)

				if data[0] == 0:
					level, min_level, cards, icons = data[1:]

					print(
						f'{get_time()} {Fore.GREEN}[Profiles] ✓ Got data for {username}: level={level}, cards={len(cards)}, icons={len(icons)}{Style.RESET_ALL}',
						flush=True
					)

					player_idx = None

					for i, p in enumerate(self.PLAYERS):
						if p.get('name') == username:
							player_idx = i

							break

					if player_idx is not None:
						self.PLAYERS[player_idx]['level'] = level
						self.PLAYERS[player_idx]['min_level'] = min_level

					if cards:
						self.write_cards(username, cards)

					if icons:
						self.write_icons(username, icons)

					self.save_cards()
					self.save_icons()

					print(
						f'{get_time()} {Fore.GREEN}[Profiles] ✓ Saved cards/icons for {username}{Style.RESET_ALL}',
						flush=True
					)

				else:
					print(
						f'{get_time()} {Fore.RED}[Profiles] ✗ Failed to get data for {username}: {data[0]}{Style.RESET_ALL}',
						flush=True
					)
			except Exception as e:
				print(
					f'{get_time()} {Fore.RED}[Profiles] ✗ Exception fetching {username}: {e}{Style.RESET_ALL}',
					flush=True
				)
				traceback.print_exc()
			finally:
				if username in self._fetching_users:
					self._fetching_users.remove(username)

				print(
					f'{get_time()} {Fore.CYAN}[Profiles] Thread finished for {username}{Style.RESET_ALL}',
					flush=True
				)

		threading.Thread(target=_job, daemon=True).start()

	def storm(self):
		PLAYERS_OLD = deepcopy(self.PLAYERS)

		self.PLAYERS = []

		for _ in range(16):
			self.PLAYERS.append(
				{
					'name': None,
					'level': -1,
					'min_level': -1,
					'role': None,
					'team': None,
					'teams_exclude': set(),
					'aura': None,
					'dead': False,
					'equal': set(),
					'not_equal': set(),
					'hero': False,
					'messages': [],
					'mentions': []
				}
			)

		for p in range(16):
			for o, old in enumerate(PLAYERS_OLD):
				current_name = self.PLAYERS[p].get('name')

				if current_name and current_name == old['name']:
					self.PLAYERS[p] = old

					PLAYERS_OLD.pop(o)

					break

	def revert(self, action):
		if not self.PREV_PLAYERS:
			return -1

		else:
			self.PLAYERS = deepcopy(self.PREV_PLAYERS[-1])

			if action:
				self.PREV_PLAYERS.pop()

		return -1

	def set_name(self, player, name, threaded=False):
		data = self.get_player(name)

		if data[0] == 404:
			return 404

		elif data[0]:
			return data[0]

		level, min_level, cards, icons = data[1:]

		self.PLAYERS[player]['name'] = name

		if self.PLAYERS[player]['hero']:
			return

		self.PLAYERS[player]['level'] = level
		self.PLAYERS[player]['min_level'] = min_level

		self.write_cards(name, cards)
		self.write_icons(name, icons)

		role = self.PLAYERS[player]['role']

		if role and role not in self.ADVANCED_ROLES:
			for src_role in self.ADVANCED_ROLES:
				if role in self.ADVANCED_ROLES[src_role]:
					self.write_cards(name, {src_role: role})

					break

		if not threaded:
			self.save_cards()
			self.save_icons()

	def set_role(self, player, role):
		for r in range(len(self.ROTATION)):
			if role.lower() == self.ROTATION[r]['name'].lower():
				break

			elif self.ROTATION[r]['id'] in self.RANDOM_ROLE_TYPES:
				type_roles = self.RANDOM_ROLE_TYPES[self.ROTATION[r]['id']]
				dst_role = None

				if type(type_roles) == str:
					for role1 in self.ROLES:
						if role.lower() == self.ROLES[role1]['name'].lower():
							if self.ROLES[role1]['team'] == type_roles:
								dst_role = self.ROLES[role1]

							break

				else:
					for random_role in type_roles:
						if role.lower() == self.ROLES[random_role]['name'].lower():
							dst_role = self.ROLES[random_role]

							break

						elif random_role in self.ADVANCED_ROLES:
							for advanced_role in self.ADVANCED_ROLES[random_role]:
								if (
									role.lower()
									== self.ROLES[advanced_role]['name'].lower()
								):
									dst_role = self.ROLES[advanced_role]

									break

							if dst_role:
								break

				if dst_role:
					self.change_role(self.ROTATION[r]['name'], dst_role['name'])

					break

		else:
			return 1

		self.PLAYERS[player]['role'] = self.ROTATION[r]['id']
		self.PLAYERS[player]['team'] = self.ROTATION[r]['team']
		self.PLAYERS[player]['aura'] = self.ROTATION[r]['aura']

		for equal_player in self.PLAYERS[player]['equal']:
			if equal_player < len(self.PLAYERS):
				self.PLAYERS[equal_player]['team'] = self.PLAYERS[player]['team']

		for not_equal_player in self.PLAYERS[player]['not_equal']:
			if not_equal_player < len(self.PLAYERS):
				self.PLAYERS[not_equal_player]['teams_exclude'].add(
					self.PLAYERS[player]['team']
				)

		if self.PLAYERS[player]['hero'] or self.ROTATION[r]['id'] == 'zombie':
			return

		name = self.PLAYERS[player]['name']

		if name and self.ROTATION[r]['id'] not in self.ADVANCED_ROLES:
			for src_role in self.ADVANCED_ROLES:
				if self.ROTATION[r]['id'] in self.ADVANCED_ROLES[src_role]:
					break

			self.write_cards(name, {src_role: self.ROTATION[r]['id']})
			self.save_cards()

		if self.ROTATION[r]['id'] in self.ROTATION_ICONS:
			self.write_icons(
				name,
				{self.ROTATION[r]['id']: self.ROTATION_ICONS[self.ROTATION[r]['id']]},
			)
			self.save_icons()

	def change_role(self, src_role, dst_role):
		is_random = False

		for role in self.ROLES:
			if self.ROLES[role]['name'].lower() == dst_role.lower():
				dst_role = self.ROLES[role]
				dst_role['id'] = role

				break

		else:
			return

		for r, role in enumerate(self.ROTATION):
			if role['name'].lower() == src_role.lower():
				src_role = role['id']

				if 'random' in src_role:
					is_random = True

				break

		else:
			return

		self.ROTATION[r] = dst_role
		self.ROTATION[r]['id'] = dst_role['id']

		for p, player in enumerate(self.PLAYERS):
			if self.PLAYERS[p]['role'] == src_role:
				self.PLAYERS[p]['role'] = dst_role['id']
				self.PLAYERS[p]['team'] = dst_role['team']
				self.PLAYERS[p]['aura'] = dst_role['aura']

				if (
					player['name']
					and not player['hero']
					and not is_random
					and dst_role['id'] not in self.ADVANCED_ROLES
				):
					self.write_cards(player['name'], {src_role: dst_role['id']})

				break

		self.save_cards()

	def remove_role(self, player, role):
		player = self.PLAYERS[player]['name']

		if not player:
			return

		if role in self.PLAYER_CARDS.get(player, {}):
			self.PLAYER_CARDS[player].pop(role)

		else:
			for card in self.PLAYER_CARDS.get(player, {}):
				if role in self.PLAYER_CARDS[player][card]:
					self.PLAYER_CARDS[player][card].remove(role)

		if role in self.PLAYER_ICONS.get(player, {}):
			self.PLAYER_ICONS[player].pop(role)

		self.save_cards()
		self.save_icons()

	def set_cursed(self):
		for r, role in enumerate(self.ROTATION):
			if role['id'] == 'cursed':
				self.ROTATION[r] = self.ROLES['werewolf']
				self.ROTATION[r]['id'] = role['id']

				break

		for r, player in enumerate(self.PLAYERS):
			if player['role'] == 'cursed':
				self.PLAYERS[r]['role'] = 'werewolf'
				self.PLAYERS[r]['team'] = 'WEREWOLF'
				self.PLAYERS[r]['aura'] = 'EVIL'

				for equal_player in list(self.PLAYERS[r]['equal']):
					if equal_player < len(self.PLAYERS):
						self.PLAYERS[equal_player]['equal'].remove(r)

				for not_equal_player in list(self.PLAYERS[r]['not_equal']):
					if not_equal_player < len(self.PLAYERS):
						self.PLAYERS[not_equal_player]['not_equal'].remove(r)

				self.PLAYERS[r]['equal'] = set()
				self.PLAYERS[r]['not_equal'] = set()

				break

	def set_equal(self, players, equal):
		if equal:
			self.PLAYERS[players[1]]['equal'].add(players[0])
			self.PLAYERS[players[0]]['equal'].add(players[1])

			if self.PLAYERS[players[0]]['team']:
				self.PLAYERS[players[1]]['team'] = self.PLAYERS[players[0]]['team']

			elif self.PLAYERS[players[1]]['team']:
				self.PLAYERS[players[0]]['team'] = self.PLAYERS[players[1]]['team']
				self.PLAYERS[players[0]]['teams_exclude'] = self.PLAYERS[players[1]][
					'team'
				]

			if self.PLAYERS[players[0]]['teams_exclude']:
				self.PLAYERS[players[1]]['teams_exclude'] = self.PLAYERS[players[1]][
					'teams_exclude'
				]

			elif self.PLAYERS[players[1]]['teams_exclude']:
				self.PLAYERS[players[0]]['teams_exclude'] = self.PLAYERS[players[1]][
					'teams_exclude'
				]

		else:
			self.PLAYERS[players[1]]['not_equal'].add(players[0])
			self.PLAYERS[players[0]]['not_equal'].add(players[1])

			if self.PLAYERS[players[0]]['team']:
				self.PLAYERS[players[1]]['teams_exclude'].add(
					self.PLAYERS[players[0]]['team']
				)

			elif self.PLAYERS[players[1]]['team']:
				self.PLAYERS[players[0]]['teams_exclude'].add(
					self.PLAYERS[players[1]]['team']
				)

	def set_player_info(self, player, info):
		if player.isdigit() and 1 <= int(player) <= 16:
			player = int(player) - 1

		else:
			return

		if info.lower() == 'dead':
			self.PLAYERS[player]['dead'] = True

		elif info.lower() == 'alive':
			self.PLAYERS[player]['dead'] = False

		elif info.lower() in ['good', 'evil', 'unknown']:
			self.PLAYERS[player]['aura'] = info.upper()

		elif info.lower() in ['villager', 'werewolf', 'solo']:
			self.PLAYERS[player]['team'] = info.upper()

		elif info.lower().startswith('not'):
			info = info.lower().replace('not ', '', 1)

			if info in ['villager', 'werewolf', 'solo']:
				self.PLAYERS[player]['teams_exclude'].add(info.upper())

		else:
			if self.set_role(player, info):
				return

	def build_role_lookup(self):
		lookup = {}
		acronym_map = {}

		for role_id, role_data in self.ROLES.items():
			name = role_data.get('name', '')

			if not name:
				continue

			name_lower = name.lower()
			id_lower = role_id.lower()
			id_spaced = id_lower.replace('-', ' ')

			for key in (name_lower, id_lower, id_spaced):
				if key and key not in lookup:
					lookup[key] = name

			words = name_lower.replace('-', ' ').split()

			if len(words) >= 2:
				acronym = ''.join(w[0] for w in words if w)
				acronym_map.setdefault(acronym, []).append(name)

		for acronym, names in acronym_map.items():
			unique = list(dict.fromkeys(names))

			if len(unique) == 1 and acronym not in lookup:
				lookup[acronym] = unique[0]

		return lookup

	def resolve_role_text(self, text, role_lookup):
		text = text.lower().strip().rstrip('.,!? ')

		if not text or len(text) < 2:
			return

		if text in role_lookup:
			return role_lookup[text]

		normed = text.replace(' ', '-')

		if normed in role_lookup:
			return role_lookup[normed]

		if len(text) >= 3:
			matches = []

			for key, name in role_lookup.items():
				if key.startswith(text):
					matches.append(name)

			unique_matches = list(dict.fromkeys(matches))

			if len(unique_matches) == 1:
				return unique_matches[0]

	def parse_chat_messages(self, player_messages=None):
		if player_messages is None:
			player_messages = []
			for i, p in enumerate(self.PLAYERS):
				name = p.get('name') or str(i + 1)
				for msg in p.get('messages', []):
					if isinstance(msg, str):
						player_messages.append(f'{i + 1} {name}: {msg}')
		role_lookup = self.build_role_lookup()

		rotation_counts = {}

		for slot in self.ROTATION:
			rid = slot.get('id') if isinstance(slot, dict) else slot

			if rid:
				rotation_counts[rid] = rotation_counts.get(rid, 0) + 1

		unique_role_ids = {rid for rid, cnt in rotation_counts.items() if cnt == 1}

		aura_map = {
			'good': 'GOOD',
			'evil': 'EVIL',
			'bad': 'EVIL',
			'unk': 'UNKNOWN',
			'unknown': 'UNKNOWN'
		}

		patterns = {
			'self_claim': re.compile(
				r"^(?:i'?m|i am|iam|my role is)\s+([\w][\w\s\-]{1,25}?)(?:\s*$|[,\.!?\s])"
				r"|^([\w][\w\s\-]{1,20}?)\s+here\b"
				r"|^([\w][\w\s\-]{1,20}?)\s+claim\b"
			),
			'player_role': re.compile(
				r'\b(\d{1,2})\s+(?:is\s+|=\s*)?([\w][\w\-]{1,25}?)(?:\s*$|[,\.!?\s])'
			),
			'spirit_seer': re.compile(
				r'\b(\d{1,2})\s*[&,]\s*(\d{1,2})\s+(?:is\s+|are\s+)?(red|blue)\b'
			),
			'aura_result': re.compile(
				r'\b(\d{1,2})\s+(?:is\s+)?(good|evil|bad|unk\b|unknown)\b'
			),
			'doctor_on': re.compile(
				r'(?:doc(?:tor)?\s+on|protecting|heal(?:ing)?|sav(?:ed?|ing)|bg\s+(?:here\s+)?saved?)\s+(\d{1,2}|\bme\b)\b'
			),
			'jailer_on': re.compile(
				r'(?:jail(?:ing|ed)?|warden\s+jail)\s+(\d{1,2})\b'
			),
			'vigilante_action': re.compile(
				r'(?:vigi(?:lante)?\s+(?:open|shoot|kill)|shoot(?:ing)?\s+(\d{1,2})|\b(\d{1,2})\s+open\b)'
			)
		}

		unique_claims = {}

		self.PLAYER_ALLIANCES = {}

		for p in self.PLAYERS:
			for key in ('contradiction',):
				if key in p:
					del p[key]

		def get_claims(name):
			if name not in self.PLAYER_CLAIMS:
				self.PLAYER_CLAIMS[name] = {}

			return self.PLAYER_CLAIMS[name]

		def resolve_role(text):
			return self.resolve_role_text(text, role_lookup)

		def record_aura(target_num, aura_str, claimer_name):
			aura = aura_map.get(aura_str.lower().rstrip('.'), 'UNKNOWN')

			if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
				get_claims(claimer_name).setdefault('aura_claims', {})[target_num + 1] = aura

		for msg_text in player_messages:
			try:
				prefix, message = msg_text.split(': ', 1)
				parts = prefix.split(' ', 1)
				player_num = int(parts[0]) - 1
				player_name = parts[1]
			except (ValueError, IndexError):
				continue

			ml = message.lower().strip()

			m = patterns['spirit_seer'].search(ml)

			if m:
				result = 'KILLER' if m.group(3) == 'red' else 'INNOCENT'

				for grp in (1, 2):
					t = int(m.group(grp)) - 1

					if 0 <= t < 16 and self.PLAYERS[t]['name']:
						get_claims(player_name).setdefault('spirit_checks', {})[t + 1] = result
				
				continue

			m = patterns['aura_result'].search(ml)

			if m:
				record_aura(int(m.group(1)) - 1, m.group(2), player_name)

			m = patterns['self_claim'].search(ml)

			if m:
				role_text = m.group(1) or m.group(2) or m.group(3)

				if role_text:
					role_name = resolve_role(role_text.strip())

					if role_name:
						get_claims(player_name)['role'] = role_name

			for m in patterns['player_role'].finditer(ml):
				t = int(m.group(1)) - 1

				role_text = m.group(2)

				if role_text in aura_map:
					continue

				role_name = resolve_role(role_text)

				if role_name and 0 <= t < 16 and self.PLAYERS[t]['name']:
					claims = get_claims(self.PLAYERS[t]['name'])
					claims['role'] = role_name
					claims['claimed_by'] = player_name

			m = patterns['doctor_on'].search(ml)

			if m:
				target_raw = m.group(1)

				if target_raw and target_raw != 'me':
					t = int(target_raw) - 1

					if 0 <= t < 16 and self.PLAYERS[t]['name']:
						target_name = self.PLAYERS[t]['name']
						alliances = self.PLAYER_ALLIANCES.setdefault(player_name, {})
						alliances[target_name] = alliances.get(target_name, 0) + 1

				elif target_raw == 'me':
					alliances = self.PLAYER_ALLIANCES.setdefault(player_name, {})
					alliances[player_name] = alliances.get(player_name, 0) + 1

			m = patterns['jailer_on'].search(ml)

			if m:
				t = int(m.group(1)) - 1

				if 0 <= t < 16 and self.PLAYERS[t]['name']:
					get_claims(player_name).setdefault('jailed', []).append(t + 1)

			m = patterns['vigilante_action'].search(ml)

			if m:
				target = m.group(1) or m.group(2)

				if target:
					t = int(target) - 1

					if 0 <= t < 16 and self.PLAYERS[t]['name']:
						get_claims(player_name).setdefault('shot_at', []).append(t + 1)

		for player_name, claim_data in self.PLAYER_CLAIMS.items():
			role_name = claim_data.get('role')

			if not role_name:
				continue

			role_id = None

			for rid, rdata in self.ROLES.items():
				if rdata['name'].lower() == role_name.lower():
					role_id = rid

					break

			if not role_id or role_id not in unique_role_ids:
				continue

			if role_id in unique_claims:
				original = unique_claims[role_id]

				for p in self.PLAYERS:
					if p['name'] in (player_name, original):
						p['contradiction'] = role_name

			else:
				unique_claims[role_id] = player_name

	def calculate_threats(self):
		if not self.mastermind or not self.mastermind.profiles:
			self.THREAT_LEVELS = {}

			return

		state = self.mastermind.state
		lynch_scores = self.mastermind.calculate_lynch_scores(state)
		scenarios = self.mastermind.predict(max_depth=2)

		death_probs = {p['name']: 0.0 for p in self.PLAYERS if p.get('name') and not p.get('dead')}

		for scenario in scenarios[:15]:
			dead_in_this_scenario = set()

			for action in scenario.get('path', [])[:2]:
				ability_type = action['ability'].get('type', '')
				
				if 'kill' in ability_type or 'ignite' in ability_type or 'lynch' in ability_type:
					target = action.get('target')
					
					if not target:
						continue
					
					targets_to_process = [target] if isinstance(target, dict) else list(target)
					
					for t in targets_to_process:
						dead_in_this_scenario.add(t['name'])
			
			for dead_player_name in dead_in_this_scenario:
				if dead_player_name in death_probs:
					death_probs[dead_player_name] += scenario['prob']

		raw_threats = {}
		living_players = [p['name'] for p in self.PLAYERS if p.get('name') and not p.get('dead')]

		for name in living_players:
			social_threat = lynch_scores.get(name, 100)

			death_prob = death_probs.get(name, 0.0)
			survivability_score = 1.0 - death_prob
			
			raw_threats[name] = social_threat * (1 + survivability_score)

		max_threat = max(raw_threats.values()) if raw_threats else 0
		
		self.THREAT_LEVELS = {}

		if max_threat > 0:
			for name, raw_score in raw_threats.items():
				normalized_threat = (raw_score / max_threat) * 99

				self.THREAT_LEVELS[name] = int(min(100, max(1, normalized_threat)))

	def compute_remaining(self):
		remaining = {'GOOD': [], 'EVIL': [], 'UNKNOWN': []}
		distinct_rotation = []

		for role in self.ROTATION:
			if role not in distinct_rotation:
				distinct_rotation.append(role)

		for role in distinct_rotation:
			total = self.ROTATION.count(role)
			found = 0

			for player in self.PLAYERS:
				if player['role'] == role['id']:
					found += 1

					if found == total:
						break

			for _ in range(total - found):
				remaining[role['aura']].append(role['name'])

		return remaining

	def monitor(self):
		module_name = self.__class__.__name__

		if self.mastermind and self.mastermind.profiles:
			module_name += f' {Fore.YELLOW}/ with {Fore.RED}Mastermind{Fore.RESET}'

		banner(module_name)
		players_info = ''
		remaining = self.compute_remaining()
		remaining_good = ', '.join(remaining['GOOD'])
		remaining_evil = ', '.join(remaining['EVIL'])
		remaining_unknown = ', '.join(remaining['UNKNOWN'])
		remaining_info = (
			f'\n{Style.BRIGHT}{Back.RED}REMAINING{Back.RESET}'
			+ f'\n{Fore.GREEN}GOOD:{Fore.RESET} {remaining_good}'
			+ f'\n{Fore.RED}EVIL:{Fore.RESET} {remaining_evil}'
			+ f'\n{Fore.CYAN}UNKNOWN:{Fore.RESET} {remaining_unknown}'
		)

		for i, player in enumerate(self.PLAYERS):
			name = player['name']
			level = player['level']
			min_level = player['min_level']
			team = player['team']
			teams_exclude = player['teams_exclude']
			aura = player['aura']
			messages = player['messages']
			cards = list(self.PLAYER_CARDS.get(name, {}).values()) if name else []

			flatten_cards = []

			for c in cards:
				if type(c) == list:
					flatten_cards.extend(c)

				else:
					flatten_cards.append(c)

			cards = flatten_cards
			icons = self.PLAYER_ICONS.get(name, {}) if name else {}
			possible = []

			if not player['role']:
				for role in self.ROTATION:
					if 'random' in role['id']:
						continue

					player_icon = icons.get(role['id'])
					role_icon = self.ROTATION_ICONS.get(role['id'])
					base_test = [
						role['team'] not in teams_exclude,
						not team or team == role['team'],
						not aura or aura == role['aura'],
						self.ROLES[role['id']]['name'] in remaining[role['aura']]
					]
					role_test = [
						role['id'] in cards,
						not player_icon or player_icon == role_icon
					]

					if all(base_test) and all(role_test):
						possible.append(
							{
								'role': self.ROLES[role['id']]['name'],
								'has_card': role['id'] in cards,
								'has_icon': player_icon == role_icon
							}
						)

			info = f'{i + 1}'

			if name:
				info += f' {name}'

			if level != -1:
				info += f' {Fore.YELLOW}⭐{level}{Fore.RESET}'

			elif min_level != -1:
				info += f' {Fore.YELLOW}⭐{min_level}+{Fore.RESET}'

			info += f' ({len(messages)})'
			player_claim = self.PLAYER_CLAIMS.get(name, {}) if name else {}

			if not player['role']:
				if player_claim.get('role'):
					info += f' {Fore.CYAN}C: {player_claim["role"]}{Style.RESET_ALL}'

				if player.get('contradiction'):
					role = player['contradiction']
					info += f' {Back.RED}{Style.BRIGHT}CC: {role}{Style.RESET_ALL}'

			for protector, targets in self.PLAYER_ALLIANCES.items():
				for target, count in targets.items():
					if target == name:
						info += (
							f' {Fore.BLUE}🛡️ by {protector} (x{count}){Style.RESET_ALL}'
						)

			if player['role']:
				role = self.ROLES[player['role']]['name']
				info += f' - {role}'

			elif team:
				info += f' [{team}]'

			elif teams_exclude:
				teams_exclude = ', '.join(teams_exclude)
				info += f' [NOT {teams_exclude}]'

			if possible:
				info += ' + POSSIBLE '

				for p in range(len(possible)):
					role = possible[p]['role']
					has_card = possible[p]['has_card']
					has_icon = possible[p]['has_icon']
					info += role

					if not has_card and not has_icon:
						info += ' ❌⭕'

					elif not has_card:
						info += ' ❌'

					elif not has_icon:
						info += ' ⭕'

					if p != len(possible) - 1:
						info += ' / '

			threat = self.THREAT_LEVELS.get(name) if name else None

			if threat is not None:
				threat_color = Fore.GREEN

				if 30 <= threat < 70:
					threat_color = Fore.YELLOW

				elif threat >= 70:
					threat_color = Fore.RED

				info += f' {threat_color}[{threat}% ❕]{Fore.RESET}'

			if player['aura'] == 'GOOD':
				info = f'{Back.GREEN}{info}{Back.RESET}'

			elif player['aura'] == 'EVIL':
				info = f'{Back.RED}{info}{Back.RESET}'

			elif player['aura'] == 'UNKNOWN':
				info = f'{Back.CYAN}{info}{Back.RESET}'

			if player['dead']:
				info = f'\t{Style.DIM}{info}{Style.NORMAL}'

			else:
				info = f'{Style.BRIGHT}{info}'

			info += '\n'
			players_info += info

		print(f'{Style.BRIGHT}{players_info}{remaining_info}', flush=True)

	def predict(self, player_name=None):
		if not self.mastermind or not self.mastermind.profiles:
			print(f'\n{Back.RED}{Style.BRIGHT}Mastermind is not ready!{Back.RESET}')
			
			return

		if not player_name:
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Calculating scenarios...{Fore.RESET}')

		else:
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Calculating scenarios with focus on {player_name}...{Fore.RESET}')

		self.mastermind.update_state()

		scenarios = self.mastermind.predict(max_depth=3, prob_threshold=0.01, player_name=player_name)

		if not scenarios:
			print(f'{Style.BRIGHT}{Fore.YELLOW}No viable scenarios found.{Fore.RESET}')

			return
		
		print()

		for i, scenario in enumerate(scenarios[:5]):
			path_parts = []

			if scenario['path']:
				for action in scenario['path']:
					actor_name = action['actor']['name']
					ability = action['ability']
					ability_desc = ability['description']
					ability_type = ability.get('type', '')
					target = action.get('target')
					
					desc_color = Fore.WHITE
					
					if 'kill' in ability_type or 'lynch' in ability_type or 'ignite' in ability_type:
						desc_color = Fore.RED

					elif 'protect' in ability_type:
						desc_color = Fore.BLUE

					elif 'investigate' in ability_type or 'check' in ability_type:
						desc_color = Fore.CYAN

					target_text = ''

					if target:
						if isinstance(target, tuple):
							target_names = f'{Fore.YELLOW}, '.join([t['name'] for t in target])
							target_text = f' -> ({Fore.YELLOW}{target_names}{Style.RESET_ALL})'
						
						else:
							target_text = f' -> {Fore.YELLOW}{target["name"]}{Style.RESET_ALL}'
					
					path_parts.append(f'{Fore.GREEN}{actor_name}{Style.RESET_ALL}({desc_color}{ability_desc}{Style.RESET_ALL}{target_text})')
			
			path_text = f' {Fore.WHITE}->{Style.RESET_ALL} '.join(path_parts) if path_parts else f'{Fore.YELLOW}Initial State{Style.RESET_ALL}'

			print(f'{Style.BRIGHT}{Fore.GREEN}Scenario #{i + 1} ({Fore.YELLOW}{scenario["prob"]:.2%}{Fore.GREEN}):{Style.RESET_ALL}{path_text}')

		best_textategy = self.mastermind.optimize_strategy(scenarios)

		if best_textategy['action']:
			action = best_textategy['action']
			actor, ability, target = action['actor'], action['ability'], action.get('target')

			desc_color = Fore.WHITE
			ability_type = ability.get('type', '')

			if 'kill' in ability_type or 'lynch' in ability_type or 'ignite' in ability_type:
				desc_color = Fore.RED

			elif 'protect' in ability_type:
				desc_color = Fore.BLUE

			elif 'investigate' in ability_type or 'check' in ability_type:
				desc_color = Fore.CYAN
			
			target_text = ''

			if target:
				if isinstance(target, tuple):
					target_names = f'{Fore.YELLOW}, '.join([t['name'] for t in target])
					target_text = f' -> ({Fore.YELLOW}{target_names}{Style.RESET_ALL})'

				else:
					target_text = f' -> {Fore.YELLOW}{target["name"]}{Style.RESET_ALL}'

			print(f'\n{Style.BRIGHT}{Fore.GREEN}Recommended Action: {Fore.GREEN}{actor["name"]}{Style.RESET_ALL}({desc_color}{ability["description"]}{Style.RESET_ALL}{target_text})')
			print(f'{Style.BRIGHT}{Fore.GREEN}Success Probability: {Fore.YELLOW}{best_textategy["expected_success"]*100:.2f}%{Style.RESET_ALL}')

		return

	def debug_mastermind(self):
		print(
			f'\n{Fore.CYAN}{Style.BRIGHT}--- STARTING MASTERMIND DEBUG ---{Fore.RESET}',
			flush=True
		)

		mind = self.mastermind

		if not mind or not mind.profiles:
			print(
				f'{Back.RED}{Style.BRIGHT}Mastermind is not initialized.{Back.RESET}',
				flush=True
			)

			return

		mind.update_state()
		state = mind.state

		print(f'{Style.BRIGHT}Step 1: Initializing simulation state', flush=True)

		alive_players = [p for p in state.players if not p['dead'] and p['role']]

		if not alive_players:
			print(
				f'{Back.YELLOW}{Fore.BLACK}No living players with known roles found for analysis.{Back.RESET}',
				flush=True
			)

			return

		print(
			f'\n{Style.BRIGHT}Step 2: Searching for potentially active players',
			flush=True
		)

		print(f'  - Found living players with roles: {len(alive_players)}', flush=True)
		
		total_actions_found = 0

		for player in alive_players:
			print(
				f'\n{Fore.GREEN}--- Analyzing Player: {player["name"]} (Role: {player["role"]}) ---{Fore.RESET}',
				flush=True
			)

			abilities = mind.profiles.get(player['role'])

			if not abilities:
				print(
					f'  - {Back.RED}ERROR:{Back.RESET} Abilities for role \"{player["role"]}\" not found in role profiles!',
					flush=True
				)

				continue

			print(f'  - Abilities found in profile: {len(abilities)}', flush=True)

			for i, ability in enumerate(abilities):
				ability_type = ability.get('type', 'N/A')

				print(f'    {i + 1}) Ability "{ability_type}":', flush=True)

				is_valid = mind.is_ability_valid(player, ability, state)

				if not is_valid:
					reason = 'max uses exceeded'

					print(
						f'    - {Fore.YELLOW}Validity Check: FAILED (Reason: {reason}){Fore.RESET}',
						flush=True
					)

					continue

				print(
					f'    - {Fore.GREEN}Validity Check: PASSED{Fore.RESET}', flush=True
				)

				targets = mind.get_potential_targets(
					player, ability.get('targets', {}), state
				)

				if not targets:
					print(
						f'    - {Fore.YELLOW}Target Search: No valid targets found.{Fore.RESET}',
						flush=True
					)

					continue

				target_names = [t['name'] for t in targets]

				print(
					f'    - {Fore.GREEN}Target Search: Found {len(targets)} targets ({", ".join(target_names)}){Fore.RESET}',
					flush=True
				)

				total_actions_found += len(targets)

		print(f'\n{Style.BRIGHT}--- DEBUG SUMMARY ---{Style.BRIGHT}', flush=True)

		if total_actions_found > 0:
			print(
				f'{Fore.GREEN}Mastermind found {total_actions_found} possible actions.{Fore.RESET}',
				flush=True
			)

		else:
			print(
				f'{Back.YELLOW}{Fore.BLACK}Mastermind found 0 possible actions.{Back.RESET}',
				flush=True
			)

		return

	def process(self, cmd):
		if not cmd:
			return

		elif cmd.lower() == 'end':
			self.reset()

			print(f'{get_time()} {Fore.YELLOW}[Game] State reset by "end" command.{Style.RESET_ALL}', flush=True)

			return 1

		elif '=' in cmd or '!=' in cmd:
			equal = '!=' if '!=' in cmd else '='
			players = cmd.split(f' {equal} ')

			if len(players) == 2 and players[0].isdigit() and players[1].isdigit():
				players = list(map(int, players))

				if not (1 <= players[0] <= 16 and 1 <= players[1] <= 16):
					return

				players[0] -= 1
				players[1] -= 1

				self.set_equal(players, equal == '=')

			return

		elif cmd.lower().startswith('name of '):
			cmd_parts = cmd.split(' ')

			if (
				len(cmd_parts) == 5
				and cmd_parts[3].lower() == 'is'
				and cmd_parts[2].isdigit()
				and 1 <= int(cmd_parts[2]) <= 16
			):
				player = int(cmd_parts[2]) - 1
				name = cmd_parts[4]

				self.set_name(player, name)

			return

		elif cmd.lower().startswith('change '):
			query = cmd.lower().split('change ')[1].split(' to ')

			if len(query) == 2:
				src_role, dst_role = query

				self.change_role(src_role, dst_role)

			return

		elif cmd.lower().startswith('remove '):
			query = cmd.lower().split('remove ')[1].split(' from ')

			if len(query) == 2:
				role, player = query

				if player.isdigit() and 1 <= int(player) <= 16:
					player = int(player) - 1

					self.remove_role(player, role)

			return

		elif cmd.lower() == 'cursed turned':
			self.set_cursed()

			return

		elif cmd.lower().startswith('clear '):
			player = cmd.lower().split('clear ')[1]

			if player.isdigit() and 1 <= int(player) <= 16:
				player = int(player) - 1
				self.PLAYERS[player]['role'] = None
				self.PLAYERS[player]['team'] = None
				self.PLAYERS[player]['teams_exclude'] = set()
				self.PLAYERS[player]['equal'] = set()
				self.PLAYERS[player]['not_equal'] = set()

			return

		elif cmd.lower() in ['undo', 'redo']:
			self.revert(cmd.lower() == 'undo')

			return -1

		elif cmd.lower() == 'debug':
			self.debug_mastermind()

			return

		else:
			try:
				player, info = cmd.lower().split(' is ')

				self.set_player_info(player, info)
			except ValueError:
				return
