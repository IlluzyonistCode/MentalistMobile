"""
SessionBackend — обёртка над Tracker + Mastermind для одного устройства.

Каждая DeviceSession создаёт свой SessionBackend.
Полностью изолирован от других сессий.
"""

import sys
import os
import logging
import time

log = logging.getLogger('backend')

# Добавляем путь к серверным модулям (tracker.py, mastermind.py и т.д.)
_SERVER_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'server')
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_SERVER_DIR))


class SessionBackend:
    def __init__(self):
        from tracker import Tracker
        from mastermind import Mastermind

        self.tracker    = Tracker()
        self.mastermind = Mastermind(self.tracker)
        self.tracker.mastermind = self.mastermind

        self._last_heavy = 0.0

    # ── Обработка WS событий игры ─────────────────────────────────────────────

    def process_ws(self, direction: str, text: str):
        self.tracker.process_ws(direction, text)

        now = time.time()
        if now - self._last_heavy > 1.0:
            self._last_heavy = now
            self.tracker.parse_chat_messages()
            if self.mastermind:
                self.mastermind.update_state()

    # ── Команды от UI ─────────────────────────────────────────────────────────

    def process_command(self, cmd: str):
        return self.tracker.process(cmd)

    # ── Авторизация (bearer token игры) ───────────────────────────────────────

    def set_auth(self, bearer: str, cfjwt: str):
        self.tracker.set_auth(bearer, cfjwt)

    # ── Predict ───────────────────────────────────────────────────────────────

    def predict(self):
        return self.tracker.predict()

    # ── Bot API key для Inviter ───────────────────────────────────────────────

    def get_bot_api_key(self) -> str:
        keys = getattr(self.tracker, 'API_KEYS', [])
        return keys[0] if keys else ''

    # ── Данные для UI ─────────────────────────────────────────────────────────

    def build_view_data(self) -> dict:
        """
        Строит полный payload для отрисовки UI на телефоне.
        Совместим со старым build_view_data из backend.py.
        """
        self.tracker.parse_chat_messages()
        self.tracker.calculate_threats()
        remaining = self.tracker.compute_remaining()

        players_data = []

        for i, player in enumerate(self.tracker.PLAYERS):
            name          = player.get('name', '')
            level         = player.get('level', -1)
            min_level     = player.get('min_level', -1)
            team          = player.get('team', '')
            teams_exclude = list(player.get('teams_exclude', set()))
            aura          = player.get('aura', '')
            role          = player.get('role', '')
            role_name     = self.tracker.ROLES.get(role, {}).get('name', '') if role else ''
            dead          = player.get('dead', False)
            messages_count = len(player.get('messages', []))

            cards = list(self.tracker.PLAYER_CARDS.get(name, {}).values()) if name else []
            flatten_cards = []
            for c in cards:
                if isinstance(c, list):
                    flatten_cards.extend(c)
                else:
                    flatten_cards.append(c)

            icons    = self.tracker.PLAYER_ICONS.get(name, {}) if name else {}
            possible = []

            if not role:
                for r in self.tracker.ROTATION:
                    if 'random' in r['id']:
                        continue
                    player_icon = icons.get(r['id'])
                    role_icon   = self.tracker.ROTATION_ICONS.get(r['id'])
                    base_test   = [
                        r['team'] not in teams_exclude,
                        not team or team == r['team'],
                        not aura or aura == r['aura'],
                        self.tracker.ROLES[r['id']]['name'] in remaining[r['aura']]
                    ]
                    role_test = [
                        r['id'] in flatten_cards,
                        not player_icon or player_icon == role_icon
                    ]
                    if all(base_test) and all(role_test):
                        possible.append({
                            'role':     self.tracker.ROLES[r['id']]['name'],
                            'has_card': r['id'] in flatten_cards,
                            'has_icon': player_icon == role_icon
                        })

            player_claim = self.tracker.PLAYER_CLAIMS.get(name, {}) if name else {}
            threat       = self.tracker.THREAT_LEVELS.get(name) if name else None

            players_data.append({
                'num':            i + 1,
                'name':           name,
                'level':          level,
                'min_level':      min_level,
                'messages':       messages_count,
                'role':           role_name,
                'team':           team,
                'teams_exclude':  teams_exclude,
                'aura':           aura,
                'dead':           dead,
                'possible':       possible,
                'claim':          player_claim.get('role', ''),
                'contradiction':  player.get('contradiction', ''),
                'threat':         threat,
                'alliances': [
                    f'{protector} (x{count})'
                    for protector, targets in self.tracker.PLAYER_ALLIANCES.items()
                    if name in targets
                    for target, count in targets.items()
                    if target == name
                ]
            })

        return {
            'players':           players_data,
            'remaining':         remaining,
            'mastermind_active': bool(self.mastermind and self.mastermind.profiles)
        }
