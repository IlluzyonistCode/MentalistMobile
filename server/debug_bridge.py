"""
DebugBridge — обработчик сообщений от Frida агента в debug режиме.
Аналог старого frida_bridge.py, очищен и упрощён.
"""

import json
import traceback
import logging
import sys
import os
from pathlib import Path
from colorama import Fore, Style

# Страховочный путь к server/ (на случай если run_debug не добавил его)
_SERVER_DIR = Path(__file__).parent.parent / 'server'
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from utils import get_time, _parse_socketio

log = logging.getLogger('debug_bridge')


class DebugBridge:
    def __init__(self, backend, session_ref: list):
        self.backend     = backend
        self._session    = session_ref   # [session] — mutable ref
        self.script      = None          # устанавливается после load()

    def on_message(self, message: dict, data):
        time_str = get_time()
        try:
            if message['type'] == 'send':
                self._handle_payload(message['payload'], time_str)

            elif message['type'] == 'error':
                print(
                    f'{time_str} {Fore.RED}[Frida Error] {message.get("description", "Unknown")}{Style.RESET_ALL}',
                    flush=True
                )
                print(
                    f'{time_str} {Fore.RED}[Stack] {message.get("stack", "")}{Style.RESET_ALL}',
                    flush=True
                )
        except Exception as e:
            print(f'{time_str} {Fore.RED}[Bridge Error] {e}{Style.RESET_ALL}', flush=True)
            traceback.print_exc()

    def _handle_payload(self, payload, time_str: str):
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                print(f'{time_str} {Fore.WHITE}[Frida Raw] {payload}{Style.RESET_ALL}', flush=True)
                return

        ptype = payload.get('type')

        if ptype == 'log':
            print(f'{time_str} {Fore.YELLOW}[Frida Log] {payload.get("message")}{Style.RESET_ALL}', flush=True)

        elif ptype == 'ws_message':
            self._handle_ws_message(payload, time_str)

        elif ptype == 'command':
            self._handle_command(payload, time_str)

        elif ptype == 'predict_request':
            self._handle_predict(time_str)

        elif ptype == 'auth':
            msg = payload.get('message', '')
            print(f'{time_str} {Fore.CYAN}[Frida Agent] {payload}{Style.RESET_ALL}', flush=True)

        elif ptype == 'http_headers':
            self._handle_http_headers(payload, time_str)

        elif ptype == 'http_request':
            method = payload.get('method', '?')
            url    = payload.get('url', '')
            print(f'{time_str} {Fore.WHITE}[HTTP] {method} {url[:120]}{Style.RESET_ALL}', flush=True)

        elif ptype == 'ws_connection':
            url = payload.get('url', '')
            print(f'{time_str} {Fore.CYAN}[Frida Agent] {payload}{Style.RESET_ALL}', flush=True)

        else:
            print(f'{time_str} {Fore.WHITE}[Frida Agent] {Style.RESET_ALL}{payload}', flush=True)

    def _handle_ws_message(self, payload: dict, time_str: str):
        direction = payload.get('direction', 'UNKNOWN')
        data      = payload.get('data', '')
        data_type = payload.get('dataType', 'Unknown')

        # Логирование
        try:
            if data_type == 'String' and isinstance(data, str):
                msg_type = 'UNKNOWN'
                if   data.startswith('0'):  msg_type = 'CONNECT'
                elif data.startswith('1'):  msg_type = 'DISCONNECT'
                elif data.startswith('2'):  msg_type = 'PING'
                elif data.startswith('3'):  msg_type = 'PONG'
                elif data.startswith('40'): msg_type = 'NAMESPACE_CONNECT'
                elif data.startswith('41'): msg_type = 'NAMESPACE_DISCONNECT'
                elif data.startswith('42'): msg_type = 'EVENT'
                elif data.startswith('43'): msg_type = 'ACK'

                color = Fore.CYAN if direction == 'INBOUND' else Fore.MAGENTA
                label = f'WS IN:{msg_type}' if direction == 'INBOUND' else f'WS OUT:{msg_type}'
                print(f'{time_str} {color}[{label}] {data[:200]}{Style.RESET_ALL}', flush=True)

                if msg_type == 'EVENT':
                    evt, p = _parse_socketio(data)
                    if evt:
                        print(f'{time_str} {Fore.GREEN}[WS Event] {evt}{Style.RESET_ALL}', flush=True)
                        self._log_event_detail(evt, p, time_str)
        except Exception as e:
            print(f'{time_str} {Fore.RED}[WS Log Error] {e}{Style.RESET_ALL}', flush=True)

        # Обработка
        try:
            if data_type == 'String' and isinstance(data, str):
                self.backend.process_ws(direction, data)
                self._push_view_data(time_str)
        except Exception as e:
            print(f'{time_str} {Fore.RED}[Backend WS Error] {e}{Style.RESET_ALL}', flush=True)
            traceback.print_exc()

    def _handle_command(self, payload: dict, time_str: str):
        cmd = payload.get('data', '') or payload.get('text', '')
        if not cmd:
            return
        try:
            result    = self.backend.process_command(cmd)
            error_msg = result if isinstance(result, str) else None
            self._push_view_data(time_str)
            if error_msg and self.script:
                self.script.exports_sync.seterror(error_msg)
        except Exception as e:
            print(f'{time_str} {Fore.RED}[Cmd Error] {e}{Style.RESET_ALL}', flush=True)

    def _handle_predict(self, time_str: str):
        try:
            result = self.backend.predict()
            if self.script:
                self.script.exports_sync.setpredictresult(result)
            print(f'{time_str} {Fore.GREEN}[Predict] Result sent{Style.RESET_ALL}', flush=True)
        except Exception as e:
            print(f'{time_str} {Fore.RED}[Predict Error] {e}{Style.RESET_ALL}', flush=True)

    def _handle_http_headers(self, payload: dict, time_str: str):
        try:
            headers = payload.get('headers', {})
            bearer  = None
            cf_jwt  = None

            auth = headers.get('Authorization') or headers.get('authorization')
            if auth and auth.startswith('Bearer '):
                bearer = auth.split(' ', 1)[1]

            for key in ['Cf-Jwt', 'cf-jwt', 'CF-JWT']:
                if key in headers:
                    cf_jwt = headers[key]
                    break

            if bearer or cf_jwt:
                self.backend.set_auth(bearer, cf_jwt)
                if bearer:
                    print(
                        f'{time_str} {Fore.CYAN}[Auth] Bearer token captured (***{bearer[-8:]}){Style.RESET_ALL}',
                        flush=True
                    )
        except Exception as e:
            print(f'{time_str} {Fore.RED}[Auth Capture Error] {e}{Style.RESET_ALL}', flush=True)

    def _push_view_data(self, time_str: str):
        if not self.script:
            return
        try:
            data = self.backend.build_view_data()
            self.script.exports_sync.setviewdata(json.dumps(data))
        except Exception as e:
            print(f'{time_str} {Fore.RED}[Render Error] {e}{Style.RESET_ALL}', flush=True)

    def _log_event_detail(self, evt: str, p, time_str: str):
        try:
            tracker = self.backend.tracker
            if evt in ('player-joined-and-equipped-items', 'player-disconnected'):
                name = ''
                if evt == 'player-joined-and-equipped-items' and p and 'player' in p:
                    name = p['player'].get('username', 'Unknown')
                elif evt == 'player-disconnected' and p:
                    pid = p.get('id')
                    num = tracker.num_by_id.get(pid)
                    if num and 1 <= num <= 16:
                        name = tracker.PLAYERS[num - 1].get('name', 'Unknown')
                print(f'{time_str} {Fore.GREEN}  └─ Player: {name}{Style.RESET_ALL}', flush=True)

            elif evt == 'game-settings-changed' and p:
                roles = p.get('roles', [])
                if roles:
                    print(
                        f'{time_str} {Fore.BLUE}  └─ Roles: {", ".join(roles[:5])}{"..." if len(roles) > 5 else ""}{Style.RESET_ALL}',
                        flush=True
                    )
        except Exception:
            pass
