import urllib3
import asyncio
import frida
import sys
import os
import json
import time
import re
import threading
import requests
import frida_tools
from datetime import datetime
from colorama import Fore, Style, Back, init
from dotenv import load_dotenv, find_dotenv, dotenv_values
from copy import deepcopy
from itertools import combinations
from functools import lru_cache

init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    env_path = find_dotenv()
    if env_path:
        load_dotenv(env_path, override=False)
        print(
            f'{datetime.now().strftime("[%H:%M:%S]")} {Fore.GREEN}Loaded .env from {env_path}{Style.RESET_ALL}',
            flush=True,
        )
    else:
        load_dotenv(override=False)
except Exception:
    pass

PACKAGE_NAME = os.environ.get('PACKAGE_NAME', 'com.mentalist.mobile')
JS_SCRIPT_PATH = os.environ.get('JS_SCRIPT_PATH', 'agent.js')
DEVICE_SERIAL = os.environ.get('DEVICE_SERIAL') or None

script = None
loop = None
session = None
backend = None
shutdown_event = threading.Event()


def get_time():
    return f'[{datetime.now().strftime("%H:%M:%S")}]'


def on_message(message, data):
    global script, loop

    time_str = get_time()

    try:
        if message['type'] == 'send':
            payload = message['payload']

            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    print(
                        f'{time_str} {Fore.WHITE}[Frida Agent] {Style.RESET_ALL}Raw Message: {payload}',
                        flush=True,
                    )
                    return

            if payload.get('type') == 'ws_message':
                direction = payload.get('direction', 'UNKNOWN')
                data_content = payload.get('data', 'N/A')
                data_type = payload.get('dataType', 'Unknown')

                try:
                    if data_type == 'String' and isinstance(data_content, str):
                        msg_type = 'UNKNOWN'
                        if data_content.startswith('0'):
                            msg_type = 'CONNECT'
                        elif data_content.startswith('1'):
                            msg_type = 'DISCONNECT'
                        elif data_content.startswith('2'):
                            msg_type = 'PING'
                        elif data_content.startswith('3'):
                            msg_type = 'PONG'
                        elif data_content.startswith('40'):
                            msg_type = 'NAMESPACE_CONNECT'
                        elif data_content.startswith('41'):
                            msg_type = 'NAMESPACE_DISCONNECT'
                        elif data_content.startswith('42'):
                            msg_type = 'EVENT'
                        elif data_content.startswith('43'):
                            msg_type = 'ACK'

                        if direction == 'INBOUND':
                            print(
                                f'{time_str} {Fore.CYAN}[WS IN:{msg_type}] {data_content[:200]}{Style.RESET_ALL}',
                                flush=True
                            )
                        else:
                            print(
                                f'{time_str} {Fore.MAGENTA}[WS OUT:{msg_type}] {data_content[:200]}{Style.RESET_ALL}',
                                flush=True
                            )
                            if msg_type == 'EVENT' and '"game-commit-suicide"' in data_content:
                                print(f'{get_time()} {Fore.YELLOW}[Game] Village flee detected. Resetting state...{Style.RESET_ALL}', flush=True)
                                if backend and backend.tracker:
                                    backend.tracker.reset()
                                    banner(f'Tracker {Fore.YELLOW}/ with {Fore.RED}Mastermind{Fore.RESET}' if backend.mastermind and backend.mastermind.profiles else 'Tracker')
                except Exception as log_err:
                    print(
                        f'{time_str} {Fore.RED}[WS Log Error] {log_err}{Style.RESET_ALL}',
                        flush=True
                    )

                try:
                    if data_type == 'String' and isinstance(data_content, str):
                        try:
                            backend.process_ws(direction, data_content)
                        except Exception as backend_err:
                            print(
                                f'{time_str} {Fore.RED}[Backend Process Error] {backend_err}{Style.RESET_ALL}',
                                flush=True
                            )
                            import traceback

                            traceback.print_exc()

                        try:
                            env = backend.tracker._parse_socketio_envelope(data_content)
                            if env:
                                evt, p = env

                                event_color = Fore.GREEN
                                if 'chat' in evt:
                                    event_color = Fore.CYAN
                                elif 'killed' in evt or 'vote' in evt:
                                    event_color = Fore.YELLOW
                                elif 'role' in evt:
                                    event_color = Fore.MAGENTA

                                print(
                                    f'{time_str} {event_color}[WS Event] {evt}{Style.RESET_ALL}',
                                    flush=True,
                                )

                                try:
                                    if evt in [
                                        'player-joined-and-equipped-items',
                                        'player-disconnected',
                                    ]:
                                        name = ''
                                        if (
                                            evt == 'player-joined-and-equipped-items'
                                            and p
                                            and 'player' in p
                                        ):
                                            name = p['player'].get(
                                                'username', 'Unknown'
                                            )
                                        elif evt == 'player-disconnected' and p:
                                            pid = p.get('id')
                                            num = backend.tracker.num_by_id.get(pid)
                                            if num and 1 <= num <= 16:
                                                player = backend.tracker.PLAYERS[
                                                    num - 1
                                                ]
                                                name = player.get('name', 'Unknown')
                                        print(
                                            f'{time_str} {Fore.GREEN}  └─ Player: {name}{Style.RESET_ALL}',
                                            flush=True,
                                        )

                                    elif evt == 'game:chat-public:msg' and p:
                                        author_id = p.get('authorId', 'system')
                                        num = backend.tracker.num_by_id.get(author_id)
                                        author_name = 'system'
                                        if num and 1 <= num <= 16:
                                            player = backend.tracker.PLAYERS[num - 1]
                                            author_name = player.get('name', 'system')
                                        msg_text = p.get('msg', '')
                                        print(
                                            f'{time_str} {Fore.CYAN}  └─ {author_name}: {msg_text}{Style.RESET_ALL}',
                                            flush=True,
                                        )

                                    elif evt == 'game-day-vote-set' and p:
                                        voter_id = p.get('voterId')
                                        target_id = p.get('targetPlayerId')
                                        voter_num = backend.tracker.num_by_id.get(
                                            voter_id
                                        )
                                        target_num = backend.tracker.num_by_id.get(
                                            target_id
                                        )
                                        voter_name = '?'
                                        target_name = '?'
                                        if voter_num and 1 <= voter_num <= 16:
                                            voter_name = backend.tracker.PLAYERS[
                                                voter_num - 1
                                            ].get('name', '?')
                                        if target_num and 1 <= target_num <= 16:
                                            target_name = backend.tracker.PLAYERS[
                                                target_num - 1
                                            ].get('name', '?')
                                        count = p.get('count', '?')
                                        print(
                                            f'{time_str} {Fore.YELLOW}  └─ {voter_name} → {target_name} (total: {count}){Style.RESET_ALL}',
                                            flush=True,
                                        )

                                    elif evt == 'game-players-killed' and p:
                                        victims = p.get('victims', [])
                                        for v in victims:
                                            target_id = v.get('targetPlayerId')
                                            cause = v.get('cause', 'unknown')
                                            target_num = backend.tracker.num_by_id.get(
                                                target_id
                                            )
                                            target_name = '?'
                                            if target_num and 1 <= target_num <= 16:
                                                target_name = backend.tracker.PLAYERS[
                                                    target_num - 1
                                                ].get('name', '?')

                                            role_info_str = ''
                                            role_id = v.get('roleId')
                                            if role_id:
                                                role_data = backend.tracker.ROLES.get(role_id)
                                                if role_data and 'name' in role_data:
                                                    role_info_str = f' as {role_data["name"]}'
                                                else:
                                                    role_info_str = f' as {role_id}'

                                            print(
                                                f'{time_str} {Fore.RED}  └─ ☠ {target_name} ({cause}){role_info_str}{Style.RESET_ALL}',
                                                flush=True,
                                            )

                                    elif evt == 'game-role-revealed' and p:
                                        pid = p.get('playerId')
                                        role_id = p.get('roleId')
                                        num = backend.tracker.num_by_id.get(pid)
                                        player_name = '?'
                                        if num and 1 <= num <= 16:
                                            player_name = backend.tracker.PLAYERS[
                                                num - 1
                                            ].get('name', '?')
                                        print(
                                            f'{time_str} {Fore.MAGENTA}  └─ {player_name} revealed as {role_id}{Style.RESET_ALL}',
                                            flush=True,
                                        )

                                    elif evt in [
                                        'game-started',
                                        'game-night-started',
                                        'game-day-started',
                                        'game-day-voting-started',
                                    ]:
                                        day = p.get('day', '?') if p else '?'
                                        phase = p.get('phase', '') if p else ''
                                        print(
                                            f'{time_str} {Fore.YELLOW}  └─ Day {day} {phase}{Style.RESET_ALL}',
                                            flush=True,
                                        )

                                    elif evt == 'game-settings-changed' and p:
                                        roles = p.get('roles', [])
                                        if roles:
                                            print(
                                                f'{time_str} {Fore.BLUE}  └─ Roles: {", ".join(roles[:5])}{"..." if len(roles) > 5 else ""}{Style.RESET_ALL}',
                                                flush=True,
                                            )
                                except Exception as detail_err:
                                    print(
                                        f'{time_str} {Fore.RED}[Event Detail Error] {detail_err}{Style.RESET_ALL}',
                                        flush=True,
                                    )

                        except Exception as parse_err:
                            print(
                                f'{time_str} {Fore.RED}[Event Parse Error] {parse_err}{Style.RESET_ALL}',
                                flush=True
                            )
                            import traceback

                            traceback.print_exc()

                        try:
                            payload_data = backend.build_view_data()
                            script.exports_sync.setviewdata(json.dumps(payload_data))
                        except Exception as e2:
                            print(
                                f'{time_str} {Fore.RED}[Render Push Error] {e2}{Style.RESET_ALL}',
                                flush=True
                            )

                except Exception as e:
                    print(
                        f'{time_str} {Fore.RED}[Backend Error] {e}{Style.RESET_ALL}',
                        flush=True,
                    )
                    import traceback

                    traceback.print_exc()

            elif payload.get('type') == 'command':
                cmd_text = payload.get('data', '') or payload.get('text', '')
                if cmd_text:
                    try:
                        result = backend.process_command(cmd_text)
                        error_msg = None
                        if isinstance(result, str):
                            error_msg = result
                        try:
                            payload_data = backend.build_view_data()
                            script.exports_sync.setviewdata(json.dumps(payload_data))
                            if error_msg:
                                script.exports_sync.seterror(error_msg)
                            print(
                                f'{time_str} {Fore.CYAN}[Render] view data pushed after command{Style.RESET_ALL}',
                                flush=True
                            )
                        except Exception as e2:
                            print(
                                f'{time_str} {Fore.RED}[Render Push Error] {e2}{Style.RESET_ALL}',
                                flush=True
                            )
                    except Exception as e:
                        error_str = str(e)
                        try:
                            script.exports_sync.seterror(error_str)
                        except:
                            pass
                        print(
                            f'{time_str} {Fore.RED}[Backend Cmd Error] {e}{Style.RESET_ALL}',
                            flush=True,
                        )

            elif payload.get('type') == 'predict_request':
                try:
                    result = backend.predict()
                    script.exports_sync.setpredictresult(result)
                    print(
                        f'{time_str} {Fore.GREEN}[Predict] Result sent to UI{Style.RESET_ALL}',
                        flush=True,
                    )
                except Exception as e:
                    error_str = f'Predict error: {str(e)}'
                    try:
                        script.exports_sync.setpredictresult(error_str)
                    except:
                        pass
                    print(
                        f'{time_str} {Fore.RED}[Predict Error] {e}{Style.RESET_ALL}',
                        flush=True,
                    )

            elif payload.get('type') == 'http_headers':
                try:
                    url = payload.get('url', '')
                    headers = payload.get('headers', {})
                    bearer = None
                    cf_jwt = None
                    auth = headers.get('Authorization') or headers.get('authorization')
                    if auth and auth.startswith('Bearer '):
                        bearer = auth.split(' ', 1)[1]

                    cf_jwt_keys = ['Cf-Jwt', 'cf-jwt', 'CF-JWT']
                    for key in cf_jwt_keys:
                        if key in headers:
                            cf_jwt = headers[key]
                            break

                    if bearer or cf_jwt:
                        backend.set_auth(bearer, cf_jwt)
                except Exception as e:
                    print(
                        f'{time_str} {Fore.RED}[Backend Auth Capture Error] {e}{Style.RESET_ALL}',
                        flush=True,
                    )

            elif payload.get('type') == 'log':
                print(
                    f'{time_str} {Fore.YELLOW}[Frida Log] {payload.get("message")}{Style.RESET_ALL}',
                    flush=True,
                )

            else:
                print(
                    f'{time_str} {Fore.WHITE}[Frida Agent] {Style.RESET_ALL}{payload}',
                    flush=True,
                )

        elif message['type'] == 'error':
            print(
                f'{time_str} {Fore.RED}[Frida Error] {message.get("description", "Unknown error")}{Style.RESET_ALL}',
                flush=True,
            )
            print(
                f'{time_str} {Fore.RED}[Stack] {message.get("stack", "No stack trace")}{Style.RESET_ALL}',
                flush=True,
            )
    except Exception as e:
        print(
            f'{time_str} {Fore.RED}[Python Error in on_message] {e}{Style.RESET_ALL}',
            flush=True,
        )
        import traceback

        traceback.print_exc()


def poll_agent_messages():
    global script
    print(
        f'{get_time()} {Fore.CYAN}[Poller] RPC polling thread started...{Style.RESET_ALL}',
        flush=True
    )

    time.sleep(0.5)

    while not shutdown_event.is_set():
        try:
            messages_json = script.exports_sync.getqueuedmessages()

            if messages_json:
                messages_list = json.loads(messages_json)

                if messages_list:
                    for msg_str in messages_list:
                        try:
                            frida_message_payload = json.loads(msg_str)
                            frida_message_envelope = {
                                'type': 'send',
                                'payload': frida_message_payload,
                            }
                            on_message(frida_message_envelope, None)
                        except Exception as inner_e:
                            print(
                                f'{get_time()} {Fore.RED}[Poller Inner Error] {inner_e} on msg {msg_str[:100]}{Style.RESET_ALL}',
                                flush=True
                            )

        except Exception as e:
            error_str = str(e).lower()
            if (
                'method not found' in error_str
                or 'unable to find method' in error_str
                or 'getqueuedmessages' in error_str
            ):
                pass
            elif 'script is destroyed' in error_str:
                print(
                    f'{get_time()} {Fore.RED}[Poller] Script destroyed, thread stopped.{Style.RESET_ALL}',
                    flush=True,
                )
                break
            else:
                print(
                    f'{get_time()} {Fore.RED}[Poller Error] {e}{Style.RESET_ALL}',
                    flush=True,
                )

        shutdown_event.wait(0.1)

    print(
        f'{get_time()} {Fore.CYAN}[Poller] RPC polling thread stopped.{Style.RESET_ALL}',
        flush=True
    )


def wrap_user_script(name, script):
    import json

    if script.startswith('📦\n'):
        return script
    return f'Script.evaluate({json.dumps(name)}, {json.dumps(script)});'


def build_final_script(raw_fragments):
    fragments = []
    next_script_id = 1
    for raw_fragment in raw_fragments:
        if raw_fragment.startswith('📦\n'):
            fragments.append(raw_fragment[2:])
        else:
            script_id = next_script_id
            next_script_id += 1
            size = len(raw_fragment.encode('utf-8'))
            fragments.append(f'{size} /frida/repl-{script_id}.js\n✄\n{raw_fragment}')
    return '📦\n' + '\n✄\n'.join(fragments)


def load_script():
    try:
        with open(JS_SCRIPT_PATH, 'r', encoding='utf-8') as f:
            script_code = f.read()
        return script_code
    except FileNotFoundError:
        print(
            f'{Fore.RED}Error: Script file not found at: {JS_SCRIPT_PATH}{Style.RESET_ALL}',
            flush=True,
        )
        sys.exit(1)
    except Exception as e:
        print(f'{Fore.RED}Error loading script: {e}{Style.RESET_ALL}', flush=True)
        sys.exit(1)


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


def banner(module=None):
    os.system('cls' if os.name == 'nt' else 'clear')
    message = f'{Style.BRIGHT}{Fore.RED}Upu{Fore.YELLOW}aut{Fore.RESET}'
    if module:
        message += f'{Fore.RED} | {module}'
    message += '\n'
    print(message, flush=True)


class GameState:
    def __init__(self, tracker):
        self.players = []
        for p_template in deepcopy(tracker.PLAYERS):
            player = {
                'name': p_template.get('name'),
                'role': p_template.get('role'),
                'team': p_template.get('team'),
                'dead': p_template.get('dead', False),
                'abilities_used': {},
                'protected': 0,
                'blocked': False,
                'jailed': False,
                'doused': False,
                'wounded': False,
                'lover': None,
                'marked_by_marksman': False,
                'recruits': [],
                'is_accomplice': False,
            }
            self.players.append(player)
        self.rotation = tracker.ROTATION
        self.pending_effects = []


class Tracker:
    def __init__(self):
        self.config = dotenv_values('.env')
        try:
            self.API_KEYS = self.config['TRACKER_API_KEYS'].split(',')
        except KeyError:
            print(
                f'{Style.BRIGHT}{Back.RED}API key(s) not found!{Back.RESET}', flush=True
            )
            sys.exit(1)
        self._api_gen = self.switch_api_key()
        self.BOT_BASE_URL = 'https://api.wolvesville.com/'
        self.BEARER_BASE_URL = 'https://core.api-wolvesville.com/'
        self.BEARER_TOKEN = None
        self.CF_JWT = None
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
                'witch',
            ],
            'random-villager-strong': [
                'detective',
                'jailer',
                'medium',
                'seer',
                'vigilante',
            ],
            'random-villager-support': [
                'doctor',
                'bodyguard',
                'ghost-lady',
                'sheriff',
                'beast-hunter',
                'bellringer',
            ],
            'random-werewolf': 'WEREWOLF',
            'random-werewolf-weak': 'WEREWOLF',
            'random-werewolf-strong': 'WEREWOLF',
            'random-support-werewolf': [
                'nightmare-werewolf',
                'wolf-shaman',
                'toxic-wolf',
            ],
            'random-killer': ['arsonist', 'bandit', 'corruptor', 'serial-killer'],
            'random-voting': ['fool'],
            'random-other': ['cupid', 'cursed'],
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
        print(
            f'{get_time()} {Fore.CYAN}[Config] PACKAGE_NAME={PACKAGE_NAME}, JS_SCRIPT_PATH={JS_SCRIPT_PATH}, DEVICE_SERIAL={"set" if DEVICE_SERIAL else "auto"}{Style.RESET_ALL}',
            flush=True,
        )
        print(
            f'{get_time()} {Fore.CYAN}[Config] TRACKER_API_KEYS count={len(self.API_KEYS)}{Style.RESET_ALL}',
            flush=True,
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
                    'mentions': [],
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

    @property
    def bot_headers(self):
        api_key = next(self._api_gen)
        return {
            'Authorization': f'Bot {api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def set_auth(self, bearer, cf_jwt):
        with self._lock:
            changed = False
            if bearer and bearer != self.BEARER_TOKEN:
                self.BEARER_TOKEN = bearer
                self.BEARER_HEADERS['Authorization'] = f'Bearer {bearer}'
                print(
                    f'{get_time()} {Fore.GREEN}[Auth] ✓ Bearer Token captured: ***{bearer[-12:]}{Style.RESET_ALL}',
                    flush=True,
                )
                changed = True
            if cf_jwt and cf_jwt != self.CF_JWT:
                self.CF_JWT = cf_jwt
                self.BEARER_HEADERS['Cf-Jwt'] = cf_jwt
                print(
                    f'{get_time()} {Fore.GREEN}[Auth] ✓ CF-JWT Token captured: {cf_jwt[:30]}...{Style.RESET_ALL}',
                    flush=True,
                )
                changed = True
            if changed:
                self.BEARER_HEADERS['Ids'] = '1'
                print(
                    f'{get_time()} {Fore.YELLOW}[Auth] Current state: Bearer={bool(self.BEARER_TOKEN)}, CF-JWT={bool(self.CF_JWT)}{Style.RESET_ALL}',
                    flush=True,
                )

    def _parse_socketio_envelope(self, text):
        if not isinstance(text, str) or not text.startswith('42'):
            return None
        i = text.find('[')
        if i < 0:
            return None
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
            return None

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
                        flush=True,
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
            banner(f'Tracker {Fore.YELLOW}/ with {Fore.RED}Mastermind{Fore.RESET}' if self.mastermind and self.mastermind.profiles else 'Tracker')
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
            pass
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

    def set_auth(self, bearer, cf_jwt):
        with self._lock:
            changed = False
            if bearer and bearer != self.BEARER_TOKEN:
                self.BEARER_TOKEN = bearer
                print(
                    f'{get_time()} {Fore.GREEN}[Auth] ✓ Bearer Token captured: ***{bearer[-12:]}{Style.RESET_ALL}',
                    flush=True,
                )
                changed = True
            if cf_jwt and cf_jwt != self.CF_JWT:
                self.CF_JWT = cf_jwt
                print(
                    f'{get_time()} {Fore.GREEN}[Auth] ✓ CF-JWT Token captured: {cf_jwt[:30]}...{Style.RESET_ALL}',
                    flush=True,
                )
                changed = True

            if changed:
                print(
                    f'{get_time()} {Fore.YELLOW}[Auth] Current state: Bearer={bool(self.BEARER_TOKEN)}, CF-JWT={bool(self.CF_JWT)}{Style.RESET_ALL}',
                    flush=True,
                )

    @property
    def bot_headers(self):
        api_key = next(self._api_gen)
        return {
            'Authorization': f'Bot {api_key}' if api_key else '',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    @property
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
                flush=True,
            )
            if not self.API_KEYS:
                print(
                    f'{get_time()} {Fore.YELLOW}[API] No TRACKER_API_KEYS provided; skipping roles fetch{Style.RESET_ALL}',
                    flush=True,
                )
                return
            r = requests.get(
                self.BOT_BASE_URL + 'roles',
                headers=self.bot_headers,
                timeout=10,
                verify=False,
            )
            if not r.ok:
                print(
                    f'{get_time()} {Fore.RED}[API] roles failed: {r.status_code}{Style.RESET_ALL}',
                    flush=True,
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
                flush=True,
            )
        except Exception as e:
            print(
                f'{get_time()} {Fore.RED}[API] roles exception: {e}{Style.RESET_ALL}',
                flush=True,
            )
            import traceback

            traceback.print_exc()

    def get_icons(self):
        try:
            print(
                f'{get_time()} {Fore.YELLOW}[API] GET roleIcons...{Style.RESET_ALL}',
                flush=True,
            )
            if not self.API_KEYS:
                print(
                    f'{get_time()} {Fore.YELLOW}[API] No TRACKER_API_KEYS provided; skipping roleIcons fetch{Style.RESET_ALL}',
                    flush=True,
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
                    flush=True,
                )
                return {}
            data = r.json()
            icons = {}
            for icon in data:
                icons[icon['id']] = {
                    'filename': icon['image']['url'].split('roleIcons/')[1],
                    'role': icon['roleId'],
                }
            print(
                f'{get_time()} {Fore.GREEN}[API] roleIcons OK: {len(icons)} items{Style.RESET_ALL}',
                flush=True,
            )
            return icons
        except Exception as e:
            print(
                f'{get_time()} {Fore.RED}[API] roleIcons exception: {e}{Style.RESET_ALL}',
                flush=True,
            )
            import traceback

            traceback.print_exc()
            return {}

    def load_cards(self):
        try:
            with open('data/cards.json', 'r', encoding='utf-8') as f:
                self.PLAYER_CARDS = json.load(f)
            print(
                f'{get_time()} {Fore.GREEN}[Storage] cards.json loaded ({len(self.PLAYER_CARDS)} players){Style.RESET_ALL}',
                flush=True,
            )
        except Exception:
            self.PLAYER_CARDS = {}
            print(
                f'{get_time()} {Fore.YELLOW}[Storage] cards.json not found, starting empty{Style.RESET_ALL}',
                flush=True,
            )

    def save_cards(self):
        if not os.path.isdir('data'):
            os.mkdir('data')
        with open('data/cards.json', 'w', encoding='utf-8') as f:
            json.dump(self.PLAYER_CARDS, f, ensure_ascii=False)

    def load_icons(self):
        try:
            with open('data/icons.json', 'r', encoding='utf-8') as f:
                self.PLAYER_ICONS = json.load(f)
            print(
                f'{get_time()} {Fore.GREEN}[Storage] icons.json loaded ({len(self.PLAYER_ICONS)} players){Style.RESET_ALL}',
                flush=True,
            )
        except Exception:
            self.PLAYER_ICONS = {}
            print(
                f'{get_time()} {Fore.YELLOW}[Storage] icons.json not found, starting empty{Style.RESET_ALL}',
                flush=True,
            )

    def save_icons(self):
        if not os.path.isdir('data'):
            os.mkdir('data')
        with open('data/icons.json', 'w', encoding='utf-8') as f:
            json.dump(self.PLAYER_ICONS, f, ensure_ascii=False)

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

    def write_icons(self, player, icons):
        if player not in self.PLAYER_ICONS:
            self.PLAYER_ICONS[player] = icons
        else:
            self.PLAYER_ICONS[player].update(icons)

    def get_player(self, username):
        ENDPOINT = f'players/search?username={username}'
        try:
            data = requests.get(
                f'{self.BOT_BASE_URL}{ENDPOINT}',
                headers=self.bot_headers,
                verify=False,
                timeout=10,
            )
            if not data.ok:
                print(
                    f'{get_time()} {Fore.RED}[API] get_player failed for {username}: {data.status_code} - {data.text[:100]}{Style.RESET_ALL}',
                    flush=True,
                )
                return data.status_code, data.text
            data = data.json()
        except Exception as e:
            print(
                f'{get_time()} {Fore.RED}[API] get_player exception for {username}: {e}{Style.RESET_ALL}',
                flush=True,
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
                    headers=self.bearer_headers,
                    verify=False,
                    timeout=10,
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
                        flush=True,
                    )
            except Exception as e:
                print(
                    f'{get_time()} {Fore.YELLOW}[API] achievements exception for {username}: {e}{Style.RESET_ALL}',
                    flush=True,
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
                flush=True,
            )
            return
        self._fetching_users.add(username)
        print(
            f'{get_time()} {Fore.GREEN}[Profiles] Starting fetch for {username}{Style.RESET_ALL}',
            flush=True,
        )

        def _job():
            try:
                print(
                    f'{get_time()} {Fore.CYAN}[Profiles] Fetching data for {username}...{Style.RESET_ALL}',
                    flush=True,
                )
                data = self.get_player(username)
                if data[0] == 0:
                    level, min_level, cards, icons = data[1:]
                    print(
                        f'{get_time()} {Fore.GREEN}[Profiles] ✓ Got data for {username}: level={level}, cards={len(cards)}, icons={len(icons)}{Style.RESET_ALL}',
                        flush=True,
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
                        flush=True,
                    )
                else:
                    print(
                        f'{get_time()} {Fore.RED}[Profiles] ✗ Failed to get data for {username}: {data[0]}{Style.RESET_ALL}',
                        flush=True,
                    )
            except Exception as e:
                print(
                    f'{get_time()} {Fore.RED}[Profiles] ✗ Exception fetching {username}: {e}{Style.RESET_ALL}',
                    flush=True,
                )
                import traceback

                traceback.print_exc()
            finally:
                if username in self._fetching_users:
                    self._fetching_users.remove(username)
                print(
                    f'{get_time()} {Fore.CYAN}[Profiles] Thread finished for {username}{Style.RESET_ALL}',
                    flush=True,
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
                    'mentions': [],
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

    def parse_chat_messages(self, player_messages=None):
        claim_patterns = {
            'role_claim_self': re.compile(
                r'^(?:i am|im|iam|my role is) ([\w\-]+)', re.I
            ),
            'player_is_role': re.compile(r'(\d{1,2}) is ([\w\-]+)', re.I),
            'seer_check': re.compile(
                r'^(?:seer on|check on) (\d{1,2}) is (good|evil|unknown)', re.I
            ),
            'doctor_protection': re.compile(r'^(?:doc on|protecting) (\d{1,2})', re.I),
        }
        unique_claims = {}
        self.PLAYER_CLAIMS = {}
        self.PLAYER_ALLIANCES = {}
        for p in self.PLAYERS:
            if 'contradiction' in p:
                del p['contradiction']
        if player_messages:
            messages_to_parse = player_messages
        else:
            messages_to_parse = []
            for i, p in enumerate(self.PLAYERS):
                for msg in p.get('messages', [])[-200:]:
                    messages_to_parse.append(f'{i+1} {p.get("name", "")}: {msg}')
        for msg_text in messages_to_parse:
            try:
                if ': ' not in msg_text:
                    continue
                player_num_str, message = msg_text.split(': ', 1)
                parts = player_num_str.split(' ', 1)
                if len(parts) < 2:
                    continue
                player_name = parts[1]
            except (ValueError, IndexError):
                continue
            message_lower = message.lower()
            for claim_type, pattern in claim_patterns.items():
                match = pattern.search(message_lower)
                if not match:
                    continue
                if claim_type == 'role_claim_self':
                    claimed_role = match.group(1)
                    if player_name not in self.PLAYER_CLAIMS:
                        self.PLAYER_CLAIMS[player_name] = {}
                    self.PLAYER_CLAIMS[player_name]['role'] = claimed_role
                elif claim_type == 'player_is_role':
                    target_num, claimed_role = int(match.group(1)) - 1, match.group(2)
                    if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
                        target_name = self.PLAYERS[target_num]['name']
                        if target_name not in self.PLAYER_CLAIMS:
                            self.PLAYER_CLAIMS[target_name] = {}
                        self.PLAYER_CLAIMS[target_name]['role'] = claimed_role
                        self.PLAYER_CLAIMS[target_name]['claimed_by'] = player_name
                elif claim_type == 'seer_check':
                    target_num, aura = int(match.group(1)) - 1, match.group(2).upper()
                    if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
                        self.PLAYERS[target_num]['aura'] = aura
                        if player_name not in self.PLAYER_CLAIMS:
                            self.PLAYER_CLAIMS[player_name] = {}
                        if 'seer_checks' not in self.PLAYER_CLAIMS[player_name]:
                            self.PLAYER_CLAIMS[player_name]['seer_checks'] = {}
                        self.PLAYER_CLAIMS[player_name]['seer_checks'][
                            target_num + 1
                        ] = aura
                elif claim_type == 'doctor_protection':
                    target_num = int(match.group(1)) - 1
                    if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
                        target_name = self.PLAYERS[target_num]['name']
                        if player_name not in self.PLAYER_ALLIANCES:
                            self.PLAYER_ALLIANCES[player_name] = {}
                        self.PLAYER_ALLIANCES[player_name][target_name] = (
                            self.PLAYER_ALLIANCES[player_name].get(target_name, 0) + 1
                        )
        unique_role_ids = {
            'seer',
            'jailer',
            'fool',
            'arsonist',
            'serial-killer',
            'mayor',
            'alpha-werewolf',
            'aura-seer',
            'detective',
        }
        for player_name, claim_data in self.PLAYER_CLAIMS.items():
            role = claim_data.get('role')
            if role in unique_role_ids:
                if role in unique_claims:
                    original_claimer_name = unique_claims[role]
                    for p in self.PLAYERS:
                        if p['name'] in [player_name, original_claimer_name]:
                            p['contradiction'] = role
                else:
                    unique_claims[role] = player_name

    def calculate_threats(self):
        if not self.mastermind or not self.mastermind.profiles:
            self.THREAT_LEVELS = {}
            return
        state = self.mastermind.state
        lynch_scores = self.mastermind.calculate_lynch_scores(state)
        scenarios = self.mastermind.predict(max_depth=2)
        death_probs = {
            p['name']: 0.0 for p in self.PLAYERS if p.get('name') and not p.get('dead')
        }
        for scenario in scenarios[:15]:
            dead_in_this_scenario = set()
            for action in scenario.get('path', [])[:2]:
                ability_type = action['ability'].get('type', '')
                if (
                    'kill' in ability_type
                    or 'ignite' in ability_type
                    or 'lynch' in ability_type
                ):
                    target = action.get('target')
                    if not target:
                        continue
                    targets_to_process = (
                        [target] if isinstance(target, dict) else list(target)
                    )
                    for t in targets_to_process:
                        if t.get('name'):
                            dead_in_this_scenario.add(t['name'])
            for dead_player_name in dead_in_this_scenario:
                if dead_player_name in death_probs:
                    death_probs[dead_player_name] += scenario['prob']
        raw_threats = {}
        living_players = [
            p['name'] for p in self.PLAYERS if p.get('name') and not p.get('dead')
        ]
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
                        self.ROLES[role['id']]['name'] in remaining[role['aura']],
                    ]
                    role_test = [
                        role['id'] in cards,
                        not player_icon or player_icon == role_icon,
                    ]
                    if all(base_test) and all(role_test):
                        possible.append(
                            {
                                'role': self.ROLES[role['id']]['name'],
                                'has_card': role['id'] in cards,
                                'has_icon': player_icon == role_icon,
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
            return 'Mastermind is not ready!'
        self.mastermind.update_state()
        scenarios = self.mastermind.predict(
            max_depth=3, prob_threshold=0.01, player_name=player_name
        )
        if not scenarios:
            return 'No viable scenarios found.'
        lines = []
        for i, scenario in enumerate(scenarios[:5]):
            path_parts = []
            if scenario['path']:
                for action in scenario['path']:
                    actor_name = action['actor']['name']
                    ability = action['ability']
                    ability_desc = ability['description']
                    target = action.get('target')
                    target_text = ''
                    if target:
                        if isinstance(target, tuple):
                            target_names = ', '.join([t['name'] for t in target])
                            target_text = f' -> ({target_names})'
                        else:
                            target_text = f' -> {target["name"]}'
                    path_parts.append(f'{actor_name}({ability_desc}{target_text})')
            path_text = ' -> '.join(path_parts) if path_parts else 'Initial State'
            prob_pct = scenario['prob'] * 100
            lines.append(f'Scenario #{i + 1} ({prob_pct:.2f}%): {path_text}')
        best_strategy = self.mastermind.optimize_strategy(scenarios)
        if best_strategy['action']:
            action = best_strategy['action']
            actor, ability, target = (
                action['actor'],
                action['ability'],
                action.get('target'),
            )
            target_text = ''
            if target:
                if isinstance(target, tuple):
                    target_names = ', '.join([t['name'] for t in target])
                    target_text = f' -> ({target_names})'
                else:
                    target_text = f' -> {target["name"]}'
            lines.append('')
            lines.append(
                f'Recommended Action: {actor["name"]}({ability["description"]}{target_text})'
            )
            success_pct = best_strategy['expected_success'] * 100
            lines.append(f'Success Probability: {success_pct:.2f}%')
        return '\n'.join(lines)

    def debug_mastermind(self):
        print(
            f'\n{Fore.CYAN}{Style.BRIGHT}--- STARTING MASTERMIND DEBUG ---{Fore.RESET}',
            flush=True,
        )
        mind = self.mastermind
        if not mind or not mind.profiles:
            print(
                f'{Back.RED}{Style.BRIGHT}Mastermind is not initialized.{Back.RESET}',
                flush=True,
            )
            return
        mind.update_state()
        state = mind.state
        print(f'{Style.BRIGHT}Step 1: Initializing simulation state', flush=True)
        alive_players = [p for p in state.players if not p['dead'] and p['role']]
        if not alive_players:
            print(
                f'{Back.YELLOW}{Fore.BLACK}No living players with known roles found for analysis.{Back.RESET}',
                flush=True,
            )
            return
        print(
            f'\n{Style.BRIGHT}Step 2: Searching for potentially active players',
            flush=True,
        )
        print(f'  - Found living players with roles: {len(alive_players)}', flush=True)
        total_actions_found = 0
        for player in alive_players:
            print(
                f'\n{Fore.GREEN}--- Analyzing Player: {player["name"]} (Role: {player["role"]}) ---{Fore.RESET}',
                flush=True,
            )
            abilities = mind.profiles.get(player['role'])
            if not abilities:
                print(
                    f'  - {Back.RED}ERROR:{Back.RESET} Abilities for role \"{player["role"]}\" not found in role profiles!',
                    flush=True,
                )
                continue
            print(f'  - Abilities found in profile: {len(abilities)}', flush=True)
            for i, ability in enumerate(abilities):
                ability_type = ability.get('type', 'N/A')
                print(f'	{i + 1}) Ability "{ability_type}":', flush=True)
                is_valid = mind.is_ability_valid(player, ability, state)
                if not is_valid:
                    reason = 'max uses exceeded'
                    print(
                        f'	  - {Fore.YELLOW}Validity Check: FAILED (Reason: {reason}){Fore.RESET}',
                        flush=True,
                    )
                    continue
                print(
                    f'	  - {Fore.GREEN}Validity Check: PASSED{Fore.RESET}', flush=True
                )
                targets = mind.get_potential_targets(
                    player, ability.get('targets', {}), state
                )
                if not targets:
                    print(
                        f'	  - {Fore.YELLOW}Target Search: No valid targets found.{Fore.RESET}',
                        flush=True,
                    )
                    continue
                target_names = [t['name'] for t in targets]
                print(
                    f'	  - {Fore.GREEN}Target Search: Found {len(targets)} targets ({", ".join(target_names)}){Fore.RESET}',
                    flush=True,
                )
                total_actions_found += len(targets)
        print(f'\n{Style.BRIGHT}--- DEBUG SUMMARY ---{Style.BRIGHT}', flush=True)
        if total_actions_found > 0:
            print(
                f'{Fore.GREEN}Mastermind found {total_actions_found} possible actions.{Fore.RESET}',
                flush=True,
            )
        else:
            print(
                f'{Back.YELLOW}{Fore.BLACK}Mastermind found 0 possible actions.{Back.RESET}',
                flush=True,
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


class Mastermind:
    def __init__(self, tracker):
        self.tracker = tracker
        self.profiles = self.load_profiles()
        self.action_history = []
        self.update_state()

    def load_profiles(self, filename='role_profiles.json'):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(
                f'{Style.BRIGHT}{Back.RED}Role profiles not found!{Back.RESET}',
                flush=True,
            )
            return {}

    def update_state(self):
        self.state = GameState(self.tracker)
        self.action_history = []
        self.initialize_special_roles(self.state)

    def initialize_special_roles(self, state):
        pass

    def get_role_strategic_value(self, role_id):
        if not role_id:
            return 5
        role_profile = self.profiles.get(role_id)
        if role_profile and 'strategic_value' in role_profile:
            return role_profile['strategic_value']
        team_map = {'VILLAGER': 10, 'WEREWOLF': -15, 'SOLO': -10}
        role_data = self.tracker.ROLES.get(role_id)
        if role_data and role_data.get('team') in team_map:
            return team_map[role_data.get('team')]
        return 5

    def calculate_lynch_scores(self, state):
        scores = {}
        original_players = {p['name']: p for p in self.tracker.PLAYERS if p.get('name')}
        living_players = [p for p in state.players if not p['dead'] and p.get('name')]
        for player in living_players:
            score = 100.0
            player_data = original_players.get(player['name'])
            if not player_data:
                scores[player['name']] = score
                continue
            known_role = player.get('role')
            known_team = player_data.get('team')
            known_aura = player_data.get('aura')
            if known_role and self.tracker.ROLES.get(known_role):
                role_info = self.tracker.ROLES.get(known_role)
                role_team = role_info.get('team')
                if role_team == 'VILLAGER':
                    score *= 0.1
                elif role_team == 'SOLO':
                    score *= 5
                elif role_team == 'WEREWOLF':
                    score *= 10.0
            elif known_team:
                if known_team == 'VILLAGER':
                    score *= 0.2
                elif known_team == 'SOLO':
                    score *= 2.5
                elif known_team == 'WEREWOLF':
                    score *= 10.0
            elif known_aura:
                if known_aura == 'GOOD':
                    score *= 0.3
                elif known_aura == 'UNKNOWN':
                    score *= 1.5
                elif known_aura == 'EVIL':
                    score *= 10.0
            msg_count = len(player_data.get('messages', []))
            if msg_count <= 2:
                score *= 1.5
            elif msg_count > 10:
                score *= 0.8
            mention_count = len(player_data.get('mentions', []))
            score *= 1 + (mention_count * 0.25)
            scores[player['name']] = max(1, score)
        return scores

    def calculate_target_priority_scores(self, actor, ability, state, lynch_scores):
        scores = {}
        ability_type = ability.get('type', '')
        for player in state.players:
            if player['dead']:
                continue
            name = player['name']
            if not name:
                continue
            base_suspicion = lynch_scores.get(name, 100)
            strategic_value = self.get_role_strategic_value(player['role'])
            if 'kill' in ability_type or 'douse' in ability_type:
                if strategic_value > 0:
                    scores[name] = strategic_value * 2 + base_suspicion
                else:
                    scores[name] = base_suspicion * 0.1
            elif 'protect' in ability_type:
                if strategic_value > 0:
                    scores[name] = strategic_value * 2 + (200 - base_suspicion)
                else:
                    scores[name] = 0
            elif 'investigate' in ability_type or 'check' in ability_type:
                if player['role']:
                    scores[name] = 0
                else:
                    scores[name] = base_suspicion
            else:
                scores[name] = base_suspicion
        return scores

    @lru_cache(maxsize=2048)
    def get_possible_actions(self, state_tuple):
        state = self.tuple_to_state(state_tuple)
        all_actions = []
        alive_players = [p for p in state.players if not p['dead'] and p.get('name')]
        lynch_scores = self.calculate_lynch_scores(state)
        for player in alive_players:
            if not player['role'] or player.get('blocked') or player.get('jailed'):
                continue
            role_abilities = self.profiles.get(player['role'], {}).get('abilities', [])
            for ability in role_abilities:
                if self.is_ability_valid(player, ability, state):
                    potential_targets = self.get_potential_targets(
                        player, ability.get('targets', {}), state
                    )
                    if potential_targets:
                        max_t = ability.get('max_targets', 1)
                        TARGET_LIMIT = 5
                        if len(potential_targets) > TARGET_LIMIT:
                            priority_scores = self.calculate_target_priority_scores(
                                player, ability, state, lynch_scores
                            )
                            sorted_targets = sorted(
                                potential_targets,
                                key=lambda p: priority_scores.get(p['name'], 0),
                                reverse=True
                            )
                            interesting_targets = sorted_targets[:TARGET_LIMIT]
                        else:
                            interesting_targets = potential_targets
                        for k in range(1, max_t + 1):
                            if len(interesting_targets) < k:
                                continue
                            for target_combo in combinations(interesting_targets, k):
                                final_target = (
                                    target_combo[0]
                                    if len(target_combo) == 1
                                    else target_combo
                                )
                                all_actions.append(
                                    {
                                        'actor': player,
                                        'ability': ability,
                                        'target': final_target,
                                    }
                                )
                    elif ability.get('max_targets', 1) == 0:
                        all_actions.append(
                            {'actor': player, 'ability': ability, 'target': None}
                        )
        total_score = sum(lynch_scores.values())
        no_lynch_score = total_score * 0.15
        total_score_with_no_lynch = total_score + no_lynch_score
        if total_score_with_no_lynch > 0:
            living_players_map = {p['name']: p for p in alive_players if p.get('name')}
            for name, score in lynch_scores.items():
                prob = score / total_score_with_no_lynch
                if prob > 0:
                    target_player = living_players_map.get(name)
                    if target_player:
                        all_actions.append(
                            {
                                'actor': {'name': 'Village', 'role': 'vote'},
                                'ability': {
                                    'description': f'Lynch {name}',
                                    'type': 'lynch',
                                    'base_prob': prob,
                                },
                                'target': target_player,
                            }
                        )
            no_lynch_prob = no_lynch_score / total_score_with_no_lynch
            all_actions.append(
                {
                    'actor': {'name': 'Village', 'role': 'vote'},
                    'ability': {
                        'description': 'No Lynch',
                        'type': 'no_lynch',
                        'base_prob': no_lynch_prob,
                    },
                    'target': None,
                }
            )
        return all_actions

    def is_ability_valid(self, player, ability, state):
        uses = player.get('abilities_used', {}).get(ability.get('type'), 0)
        if uses >= ability.get('max_uses', 1):
            return 0
        ability_type = ability.get('type')
        if player['role'] == 'instigator' and ability_type == 'kill':
            alive_recruits = [
                p
                for name in player.get('recruits', [])
                for p in state.players
                if p['name'] == name and not p['dead']
            ]
            if alive_recruits:
                return 0
        if player['role'] == 'marksman' and ability_type == 'kill':
            return player.get('marked_by_marksman', False)
        return 1

    def get_potential_targets(self, actor, constraints, state):
        targets = []
        for player in state.players:
            if not player.get('name'):
                continue
            if player['name'] == actor['name'] and not constraints.get(
                'can_target_self', False
            ):
                continue
            valid = True
            for key, val in constraints.items():
                if key == 'status' and player['dead'] != val:
                    valid = False
                    break
                if key == 'team' and player.get('team') != val:
                    valid = False
                    break
                if key == 'is_doused' and not player.get('doused'):
                    valid = False
                    break
            if valid:
                targets.append(player)
        return targets

    def get_action_signature(self, action):
        actor_name = action['actor']['name']
        ability_type = action['ability'].get('type')
        target = action.get('target')
        target_signature = None
        if isinstance(target, dict):
            target_signature = target['name'] or ''
        elif isinstance(target, tuple):
            target_signature = tuple(sorted([t['name'] or '' for t in target]))
        return (actor_name, ability_type, target_signature)

    def predict(self, max_depth=3, prob_threshold=0.01, player_name=None):
        initial_state_tuple = self.state_to_tuple(self.state)
        scenarios = [
            {
                'state_tuple': initial_state_tuple,
                'prob': 1.0,
                'path': [],
                'score': 0,
                'path_signature_set': set(),
            }
        ]
        final_scenarios = []
        for depth in range(max_depth):
            next_scenarios = []
            if not scenarios:
                break
            for scenario in scenarios:
                possible_actions = self.get_possible_actions(scenario['state_tuple'])
                if not possible_actions:
                    final_scenarios.append(scenario)
                    continue
                for action in possible_actions:
                    action_signature = self.get_action_signature(action)
                    if action_signature in scenario['path_signature_set']:
                        continue
                    new_scenario = self.apply_action(scenario, action, action_signature)
                    next_scenarios.append(new_scenario)
            scenarios = self.prune_scenarios(next_scenarios, prob_threshold)
        final_scenarios.extend(scenarios)
        for s in final_scenarios:
            s['state_obj'] = self.tuple_to_state(s['state_tuple'])

        def get_sort_key(scenario):
            score = scenario.get('score', 0)
            if player_name and scenario['path']:
                last_action = scenario['path'][-1]
                target_in_action = last_action.get('target')
                is_involved = False
                if target_in_action:
                    if isinstance(target_in_action, tuple):
                        is_involved = any(
                            t['name'] == player_name for t in target_in_action
                        )
                    else:
                        is_involved = target_in_action['name'] == player_name
                if is_involved or last_action['actor']['name'] == player_name:
                    score *= 2.0
            return score

        return sorted(final_scenarios, key=get_sort_key, reverse=True)

    def check_vengeance_deaths(self, state, dead_player=None):
        if not dead_player:
            return
        dead_player_name = dead_player['name']
        target_to_kill = next(
            (
                p
                for p in state.players
                if p.get('marked_to_die_with') == dead_player_name and not p['dead']
            ),
            None,
        )
        if target_to_kill:
            target_to_kill['dead'] = True
            self.check_lover_deaths(state, dead_player=target_to_kill)

    def apply_action(self, scenario, action, action_signature):
        state = self.tuple_to_state(scenario['state_tuple'])
        new_path = scenario['path'] + [action]
        ability = action['ability']
        prob = ability.get('base_prob', 0.8)
        actor_name = action['actor']['name']
        if actor_name == 'Village':
            actor = None
        else:
            actor = next((p for p in state.players if p['name'] == actor_name), None)
        if actor_name != 'Village' and not actor:
            return scenario
        action_target = action['target']
        targets_to_process = []
        if isinstance(action_target, tuple):
            targets_to_process.extend(action_target)
        elif action_target:
            targets_to_process.append(action_target)
        if actor:
            ability_type = ability.get('type')
            uses = actor['abilities_used'].get(ability_type, 0)
            actor['abilities_used'][ability_type] = uses + 1
        for target_data in targets_to_process:
            target = next(
                (p for p in state.players if p['name'] == target_data['name']), None
            )
            if not target:
                continue
            ability_type = ability.get('type')
            if ability_type == 'lynch':
                target['dead'] = True
                self.check_lover_deaths(state, dead_player=target)
                self.check_vengeance_deaths(state, dead_player=target)
            elif ability_type == 'jail':
                target['jailed'] = True
            elif ability_type in {'mark_for_vengeance', 'tag'}:
                for p in state.players:
                    if p.get('marked_to_die_with') == actor['name']:
                        if 'marked_to_die_with' in p:
                            del p['marked_to_die_with']
                target['marked_to_die_with'] = actor['name']
            elif 'kill' in ability_type:
                immune_roles = {
                    'arsonist',
                    'serial-killer',
                    'corruptor',
                    'bandit',
                    'werewolf',
                }
                is_killer_vs_killer = (
                    actor
                    and actor.get('team') == 'WEREWOLF'
                    and target.get('role') in immune_roles
                ) or (
                    actor
                    and actor.get('role') in immune_roles
                    and target.get('team') == 'WEREWOLF'
                )
                if is_killer_vs_killer:
                    pass
                elif target['role'] == 'stubborn-werewolf' and not target.get(
                    'wounded'
                ):
                    target['wounded'] = True
                elif target['protected'] < 1:
                    target['dead'] = True
                    self.check_lover_deaths(state, dead_player=target)
                    self.check_vengeance_deaths(state, dead_player=target)
                else:
                    target['protected'] -= 1
            elif ability_type == 'protect':
                target['protected'] += 1
            elif ability_type in {'block', 'mute'}:
                target['blocked'] = True
            elif ability_type == 'douse':
                target['doused'] = True
            elif ability_type == 'convert' and actor:
                if target['team'] == 'VILLAGER':
                    target['team'] = actor['team']
                    target['is_accomplice'] = True
                elif target['team'] == 'WEREWOLF':
                    target['dead'] = True
            elif ability_type == 'zombie_bite':
                state.pending_effects.append(
                    {'type': 'zombie_conversion', 'target': target['name'], 'delay': 2}
                )
        ability_type_no_target = ability.get('type')
        if ability_type_no_target == 'no_lynch':
            pass
        elif ability_type_no_target == 'reveal_mayor' and actor:
            actor['revealed_mayor'] = True
        elif ability_type_no_target == 'reveal_and_pacify':
            pass
        elif ability_type_no_target == 'ignite':
            for p in state.players:
                if p.get('doused'):
                    if p.get('protected') < 1:
                        p['dead'] = True
                    else:
                        p['protected'] -= 1
                    p['doused'] = False
        win_metric = self.calculate_win_metric(state)
        current_prob = scenario['prob'] * prob
        score = current_prob * win_metric
        new_signature_set = scenario['path_signature_set'].copy()
        new_signature_set.add(action_signature)
        return {
            'state_tuple': self.state_to_tuple(state),
            'prob': current_prob,
            'path': new_path,
            'score': score,
            'path_signature_set': new_signature_set,
        }

    def check_lover_deaths(self, state, dead_player=None):
        if dead_player and dead_player.get('lover'):
            lover_name = dead_player['lover']
            lover_player = next(
                (p for p in state.players if p['name'] == lover_name and not p['dead']),
                None,
            )
            if lover_player:
                lover_player['dead'] = True
                self.check_lover_deaths(state, dead_player=lover_player)
                self.check_vengeance_deaths(state, dead_player=lover_player)

    def process_pending_effects(self, state):
        remaining_effects = []
        for effect in state.pending_effects:
            effect['delay'] -= 1
            if effect['delay'] <= 0:
                target = next(
                    (p for p in state.players if p['name'] == effect['target']), None
                )
                if target:
                    if effect['type'] == 'zombie_conversion':
                        target['team'] = 'ZOMBIE'
                    elif effect['type'] == 'corruptor_kill':
                        target['dead'] = True
            else:
                remaining_effects.append(effect)
        state.pending_effects = remaining_effects

    def prune_scenarios(self, scenarios, threshold):
        if not scenarios:
            return []
        BEAM_WIDTH = 25
        sorted_scenarios = sorted(
            scenarios, key=lambda x: x.get('score', 0), reverse=True
        )
        return sorted_scenarios[:BEAM_WIDTH]

    def calculate_win_metric(self, state):
        alive = [p for p in state.players if not p['dead']]
        if not alive:
            return 0.0
        teams = [p.get('team') for p in alive]
        villager_count = teams.count('VILLAGER')
        werewolf_count = teams.count('WEREWOLF')
        if werewolf_count == 0:
            return villager_count / len(alive)
        if villager_count <= werewolf_count:
            return werewolf_count / len(alive)
        return 0.5

    def optimize_strategy(self, scenarios):
        if not scenarios:
            return {'action': None, 'expected_success': 0}
        best_scenario = max(
            scenarios,
            key=lambda x: x['prob'] * self.calculate_win_metric(x['state_obj']),
        )
        first_action = best_scenario['path'][0] if best_scenario['path'] else None
        return {
            'action': first_action,
            'expected_success': self.calculate_win_metric(best_scenario['state_obj']),
        }

    def tuple_to_state(self, state_tuple):
        players_list = []
        for p_tuple in state_tuple[0]:
            player_dict = dict(p_tuple)
            if 'abilities_used' in player_dict:
                player_dict['abilities_used'] = dict(player_dict['abilities_used'])
            players_list.append(player_dict)
        state = GameState(self.tracker)
        state.players = players_list
        state.rotation = [dict(r) for r in state_tuple[1]]
        state.pending_effects = [dict(e) for e in state_tuple[2]]
        return state

    def state_to_tuple(self, state):
        player_tuples = []
        sorted_players = sorted(state.players, key=lambda x: x.get('name') or '')
        for p in sorted_players:

            def sanitize(val):
                if isinstance(val, set):
                    return frozenset(val)
                if isinstance(val, list):
                    return tuple(val)
                if isinstance(val, dict):
                    return tuple(sorted(val.items()))
                return val

            items_tuple = tuple((k, sanitize(v)) for k, v in sorted(p.items()))
            player_tuples.append(items_tuple)
        players_tuple = tuple(player_tuples)
        rotation_tuple = tuple(tuple(sorted(role.items())) for role in state.rotation)
        pending_effects_tuple = tuple(
            tuple(sorted(effect.items())) for effect in state.pending_effects
        )
        return (players_tuple, rotation_tuple, pending_effects_tuple)


class Backend:
    def __init__(self):
        self.tracker = Tracker()
        self.mastermind = Mastermind(self.tracker)
        self.tracker.mastermind = self.mastermind

    def process_ws(self, direction, text):
        self.tracker.process_ws(direction, text)
        self.tracker.parse_chat_messages()
        if self.tracker.mastermind:
            self.tracker.mastermind.update_state()

    def process_command(self, cmd):
        result = self.tracker.process(cmd)
        return result

    def set_auth(self, bearer, cfjwt):
        self.tracker.set_auth(bearer, cfjwt)

    def predict(self):
        return self.tracker.predict()

    def build_view_data(self):
        self.tracker.parse_chat_messages()
        self.tracker.calculate_threats()
        remaining = self.tracker.compute_remaining()
        players_data = []
        for i, player in enumerate(self.tracker.PLAYERS):
            name = player.get('name', '')
            level = player.get('level', -1)
            min_level = player.get('min_level', -1)
            team = player.get('team', '')
            teams_exclude = list(player.get('teams_exclude', set()))
            aura = player.get('aura', '')
            role = player.get('role', '')
            role_name = self.tracker.ROLES.get(role, {}).get('name', '') if role else ''
            dead = player.get('dead', False)
            messages_count = len(player.get('messages', []))
            cards = (
                list(self.tracker.PLAYER_CARDS.get(name, {}).values()) if name else []
            )
            flatten_cards = []
            for c in cards:
                if isinstance(c, list):
                    flatten_cards.extend(c)
                else:
                    flatten_cards.append(c)
            icons = self.tracker.PLAYER_ICONS.get(name, {}) if name else {}
            possible = []
            if not role:
                for r in self.tracker.ROTATION:
                    if 'random' in r['id']:
                        continue
                    player_icon = icons.get(r['id'])
                    role_icon = self.tracker.ROTATION_ICONS.get(r['id'])
                    base_test = [
                        r['team'] not in teams_exclude,
                        not team or team == r['team'],
                        not aura or aura == r['aura'],
                        self.tracker.ROLES[r['id']]['name'] in remaining[r['aura']],
                    ]
                    role_test = [
                        r['id'] in flatten_cards,
                        not player_icon or player_icon == role_icon,
                    ]
                    if all(base_test) and all(role_test):
                        possible.append(
                            {
                                'role': self.tracker.ROLES[r['id']]['name'],
                                'has_card': r['id'] in flatten_cards,
                                'has_icon': player_icon == role_icon,
                            }
                        )
            player_claim = self.tracker.PLAYER_CLAIMS.get(name, {}) if name else {}
            threat = self.tracker.THREAT_LEVELS.get(name) if name else None
            players_data.append(
                {
                    'num': i + 1,
                    'name': name,
                    'level': level,
                    'min_level': min_level,
                    'messages': messages_count,
                    'role': role_name,
                    'team': team,
                    'teams_exclude': teams_exclude,
                    'aura': aura,
                    'dead': dead,
                    'possible': possible,
                    'claim': player_claim.get('role', ''),
                    'contradiction': player.get('contradiction', ''),
                    'threat': threat,
                    'alliances': [
                        f'{protector} (x{count})'
                        for protector, targets in self.tracker.PLAYER_ALLIANCES.items()
                        if name in targets
                        for target, count in targets.items()
                        if target == name
                    ],
                }
            )
        return {
            'players': players_data,
            'remaining': remaining,
            'mastermind_active': bool(self.mastermind and self.mastermind.profiles),
        }


try:
    time_str = get_time()

    print(
        f'{time_str} {Fore.WHITE}Waiting for device connection...{Style.RESET_ALL}',
        flush=True
    )

    if DEVICE_SERIAL:
        try:
            device = frida.get_device(DEVICE_SERIAL)
        except:
            print(
                f'{time_str} {Fore.YELLOW}Failed to connect to {DEVICE_SERIAL}, trying USB...{Style.RESET_ALL}',
                flush=True,
            )
            device = frida.get_usb_device(timeout=10)
    else:
        try:
            device = frida.get_usb_device(timeout=10)
        except:
            print(
                f'{time_str} {Fore.YELLOW}No USB device found, trying to enumerate network devices...{Style.RESET_ALL}',
                flush=True,
            )
            devices = frida.enumerate_devices()
            if devices:
                device = devices[0]
                print(
                    f'{time_str} {Fore.GREEN}Found network device: {device.name}{Style.RESET_ALL}',
                    flush=True,
                )
            else:
                raise Exception('No devices available (USB or network)')

    print(
        f'{time_str} {Fore.GREEN}Device connected: {device.name}{Style.RESET_ALL}',
        flush=True
    )

    print(
        f'{get_time()} {Fore.YELLOW}Loading Frida Java bridge...{Style.RESET_ALL}',
        flush=True
    )
    try:
        frida_tools_path = os.path.dirname(frida_tools.__file__)
        java_bridge_path = os.path.join(frida_tools_path, 'bridges', 'java.js')

        with open(java_bridge_path, 'r', encoding='utf-8') as f:
            java_s = f.read()
        java_s += '\n\nObject.defineProperty(globalThis, "Java", { value: bridge });'
        print(
            f'{get_time()} {Fore.GREEN}Java bridge loaded from {java_bridge_path}{Style.RESET_ALL}',
            flush=True,
        )
    except Exception as e:
        print(
            f'{get_time()} {Fore.RED}CRITICAL: Could not load Frida Java bridge.{Style.RESET_ALL}',
            flush=True,
        )
        print(f'{get_time()} {Fore.RED}Error: {e}{Style.RESET_ALL}', flush=True)
        print(
            f'{get_time()} {Fore.RED}Make sure you have `frida-tools` installed: pip install frida-tools{Style.RESET_ALL}',
            flush=True,
        )
        sys.exit(1)

    print(
        f'{get_time()} {Fore.YELLOW}Loading agent script: {JS_SCRIPT_PATH}...{Style.RESET_ALL}',
        flush=True
    )
    agent_script_raw = load_script()
    agent_script_wrapped = wrap_user_script(JS_SCRIPT_PATH, agent_script_raw)

    raw_fragments = [java_s, agent_script_wrapped]
    final_agent_code = build_final_script(raw_fragments)
    print(
        f'{get_time()} {Fore.GREEN}Agent and bridge bundled successfully.{Style.RESET_ALL}',
        flush=True
    )

    print(
        f'{get_time()} {Fore.WHITE}Attempting to attach to {PACKAGE_NAME}...{Style.RESET_ALL}',
        flush=True
    )
    print(
        f'{get_time()} {Fore.YELLOW}=== PLEASE LAUNCH THE GAME ON YOUR PHONE ==={Style.RESET_ALL}',
        flush=True
    )

    session = None
    while session is None:
        try:
            session = device.attach(PACKAGE_NAME)
        except frida.ProcessNotFoundError:
            time.sleep(1)
        except Exception as e:
            print(
                f'{get_time()} {Fore.RED}Connection error: {e}{Style.RESET_ALL}',
                flush=True,
            )
            time.sleep(1)

    print(
        f'{get_time()} {Fore.GREEN}Successfully attached to process!{Style.RESET_ALL}',
        flush=True
    )

    script = session.create_script(
        final_agent_code
    )
    script.on('message', on_message)
    script.load()

    print(
        f'{get_time()} {Fore.GREEN}Injection successful. Agent running.{Style.RESET_ALL}',
        flush=True
    )
    print(
        f'{get_time()} {Fore.CYAN}Monitoring WebSocket traffic...{Style.RESET_ALL}',
        flush=True
    )

    backend = Backend()
    print(
        f'{get_time()} {Fore.GREEN}Tracker+Mastermind backend initialized.{Style.RESET_ALL}',
        flush=True
    )

    print(
        f'{get_time()} {Fore.CYAN}Starting RPC polling thread...{Style.RESET_ALL}',
        flush=True
    )
    poller_thread = threading.Thread(
        target=poll_agent_messages, daemon=True, name='RPC-Poller'
    )
    poller_thread.start()

    def build_view_data():
        try:
            players = []
            b_players = backend.tracker.players
            id_by_num = backend.tracker.id_by_num
            roles_map = backend.tracker.ROLES
            for seat in range(1, 17):
                pid = id_by_num.get(seat)
                p = b_players.get(pid) if pid else None
                if not p:
                    players.append({'number': seat})
                    continue
                name = p.get('username')
                role_id = p.get('roleRevealed')
                role_name = None
                if role_id and roles_map:
                    r = roles_map.get(role_id)
                    role_name = r.get('name') if isinstance(r, dict) else role_id
                msg_count = 0
                for c in backend.tracker.chat[-200:]:
                    if c.get('authorId') == pid:
                        msg_count += 1
                claim_role = None
                contradiction = None
                if name:
                    cr = backend.tracker.PLAYER_CLAIMS.get(name, {})
                    claim_role = cr.get('role')
                    unique_roles = {
                        'seer',
                        'jailer',
                        'fool',
                        'arsonist',
                        'serial-killer',
                        'mayor',
                        'alpha-werewolf',
                        'aura-seer',
                        'detective',
                    }
                    if claim_role in unique_roles:
                        claimers = [
                            n
                            for n, d in backend.tracker.PLAYER_CLAIMS.items()
                            if d.get('role') == claim_role
                        ]
                        if len(claimers) > 1:
                            contradiction = claim_role
                protections = []
                for protector, targets in backend.tracker.PLAYER_ALLIANCES.items():
                    if name and name in targets:
                        count = targets[name]
                        protections.append(
                            f'{protector} (x{count})' if count > 1 else protector
                        )
                possible = []
                if name:
                    cards = backend.tracker.PLAYER_CARDS.get(name, {})
                    icons = backend.tracker.PLAYER_ICONS.get(name, {})
                    for rid in backend.tracker.roles_in_rotation:
                        if 'random' in rid:
                            continue
                        role_meta = roles_map.get(rid) or {}
                        role_name_candidate = role_meta.get('name', rid)
                        has_card = rid in cards or any(
                            rid in arr for arr in cards.values()
                        )
                        rot_icon = backend.tracker.role_icons_map.get(rid)
                        has_icon = rot_icon is not None and icons.get(rid) == rot_icon
                        possible.append(
                            {
                                'role': role_name_candidate,
                                'has_card': has_card,
                                'has_icon': has_icon,
                            }
                        )
                players.append(
                    {
                        'number': seat,
                        'name': name,
                        'level': -1,
                        'min_level': -1,
                        'role': role_id,
                        'roleName': role_name,
                        'team': None,
                        'teams_exclude': [],
                        'aura': None,
                        'dead': (p.get('alive') is False),
                        'messages_count': msg_count,
                        'possible': possible,
                        'claim_role': claim_role,
                        'contradiction': contradiction,
                        'protections': protections,
                    }
                )
            remaining = backend.tracker.compute_remaining()
            return {'players': players, 'remaining': remaining}
        except Exception:
            return {'players': [], 'remaining': {'GOOD': [], 'EVIL': [], 'UNKNOWN': []}}

    loop = asyncio.get_event_loop()

    try:
        print(
            f'{get_time()} {Fore.GREEN}--- Script running. Press Enter to exit. ---{Style.RESET_ALL}',
            flush=True,
        )
        sys.stdin.read(1)
    except KeyboardInterrupt:
        print(
            f'\n{get_time()} {Fore.YELLOW}Перехвачено (Ctrl+C). Завершение...{Style.RESET_ALL}',
            flush=True,
        )

except frida.NotSupportedError as e:
    print(f'{get_time()} {Fore.RED}Error: {e}{Style.RESET_ALL}', flush=True)
    print(
        f'{get_time()} {Fore.RED}Make sure the APK with frida-gadget is installed.{Style.RESET_ALL}',
        flush=True
    )
    sys.exit(1)
except frida.TimedOutError:
    print(
        f'{get_time()} {Fore.RED}Error: Could not find device. Make sure adb can see it (USB or WiFi).{Style.RESET_ALL}',
        flush=True
    )
    sys.exit(1)
except KeyboardInterrupt:
    print(
        f'\n{get_time()} {Fore.YELLOW}Interrupted (Ctrl+C). Shutting down...{Style.RESET_ALL}',
        flush=True
    )
except Exception as e:
    print(f'{get_time()} {Fore.RED}Unexpected error: {e}{Style.RESET_ALL}', flush=True)
    import traceback

    traceback.print_exc()
    sys.exit(1)
finally:
    time_str = get_time()

    print(
        f'{time_str} {Fore.WHITE}Stopping polling thread...{Style.RESET_ALL}',
        flush=True
    )
    shutdown_event.set()

    if session:
        print(
            f'{time_str} {Fore.WHITE}Detaching from session.{Style.RESET_ALL}',
            flush=True,
        )
        try:
            session.detach()
        except:
            pass

    print(f'{time_str} {Fore.WHITE}Shutdown complete.{Style.RESET_ALL}', flush=True)
