"""
IP Whitelist авторизация.

whitelist.txt — одна строка = один IP или CIDR.
Поддерживает:
  - точные IP: 1.2.3.4
  - CIDR подсети: 192.168.1.0/24
  - localhost всегда разрешён
  - '*' — разрешить всё (для локального debug)
"""

import ipaddress
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger('auth')

# Localhost всегда разрешён
_ALWAYS_ALLOWED = {
    '127.0.0.1', '::1', 'localhost'
}


class IPWhitelist:
    def __init__(self, path: str):
        self._path    = Path(path)
        self._lock    = threading.RLock()
        self._entries = []       # list of (str | IPv4Network | IPv6Network)
        self._allow_all = False
        self._load()

    # ── Публичный API ──────────────────────────────────────────────────────────

    def is_allowed(self, ip: str) -> bool:
        if ip in _ALWAYS_ALLOWED:
            return True

        with self._lock:
            if self._allow_all:
                return True

            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                log.warning(f'Cannot parse IP: {ip}')
                return False

            for entry in self._entries:
                if isinstance(entry, str):
                    if entry == ip:
                        return True
                else:
                    # IPv4Network / IPv6Network
                    try:
                        if addr in entry:
                            return True
                    except TypeError:
                        pass

        return False

    def add(self, ip_or_cidr: str):
        """Добавить IP/CIDR в список и сохранить на диск."""
        with self._lock:
            self._parse_and_append(ip_or_cidr)
            self._save()

    def remove(self, ip_or_cidr: str):
        with self._lock:
            before = len(self._entries)
            self._entries = [
                e for e in self._entries
                if str(e) != ip_or_cidr
            ]
            if len(self._entries) < before:
                self._save()

    def reload(self):
        self._load()

    def list_entries(self) -> list:
        with self._lock:
            return [str(e) for e in self._entries]

    # ── Внутренние ────────────────────────────────────────────────────────────

    def _load(self):
        with self._lock:
            self._entries   = []
            self._allow_all = False

            if not self._path.exists():
                log.warning(
                    f'Whitelist file not found: {self._path}. '
                    f'Creating empty file. Add IPs to allow connections.'
                )
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text('# Add allowed IPs here, one per line\n# Use * to allow all\n')
                return

            for raw_line in self._path.read_text(encoding='utf-8').splitlines():
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                if line == '*':
                    self._allow_all = True
                    log.warning('Whitelist: ALLOW ALL (*) mode — disable in production!')
                    return
                self._parse_and_append(line)

            log.info(f'Whitelist loaded: {len(self._entries)} entries from {self._path}')

    def _parse_and_append(self, value: str):
        value = value.strip()
        if '/' in value:
            try:
                net = ipaddress.ip_network(value, strict=False)
                self._entries.append(net)
            except ValueError:
                log.warning(f'Invalid CIDR in whitelist: {value}')
        else:
            try:
                ipaddress.ip_address(value)  # валидация
                self._entries.append(value)
            except ValueError:
                log.warning(f'Invalid IP in whitelist: {value}')

    def _save(self):
        lines = ['# Mentalist Server IP Whitelist', '# One IP or CIDR per line', '']
        lines += [str(e) for e in self._entries]
        self._path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
