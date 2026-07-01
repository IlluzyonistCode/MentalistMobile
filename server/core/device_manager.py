"""
DeviceManager — пул активных сессий устройств.
Thread-safe, поддерживает до max_devices одновременных подключений.
"""

import threading
import logging
from typing import Optional

log = logging.getLogger('device_manager')


class DeviceManager:
    def __init__(self, max_devices: int = 50):
        self._max     = max_devices
        self._lock    = threading.RLock()
        self._devices = {}  # device_id -> DeviceSession

    def add(self, session) -> bool:
        with self._lock:
            if len(self._devices) >= self._max:
                return False
            self._devices[session.device_id] = session
            log.info(f'DeviceManager: +{session.device_id} (total: {len(self._devices)})')
            return True

    def remove(self, device_id: str):
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                log.info(f'DeviceManager: -{device_id} (total: {len(self._devices)})')

    def get(self, device_id: str):
        with self._lock:
            return self._devices.get(device_id)

    def count(self) -> int:
        with self._lock:
            return len(self._devices)

    def list_devices(self) -> list:
        with self._lock:
            return [s.info() for s in self._devices.values()]
