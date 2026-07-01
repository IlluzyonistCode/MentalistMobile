"""
DeviceSession — изолированный контекст одного подключённого телефона.

Каждый телефон имеет свои:
- Tracker (парсинг WS событий игры)
- Mastermind (анализ ролей)
- Очередь входящих сообщений

Протокол (JSON over WebSocket):

  Телефон → Сервер:
    { "type": "ws_message",   "direction": "IN"|"OUT", "data": "...", "dataType": "String" }
    { "type": "auth",         "bearer": "...", "cfjwt": "..." }
    { "type": "command",      "data": "..." }
    { "type": "predict_req"  }
    { "type": "log",          "message": "..." }
    { "type": "ping"         }

  Сервер → Телефон:
    { "type": "view_data",    "payload": { players, remaining, ... } }
    { "type": "error",        "message": "..." }
    { "type": "predict",      "result": "..." }
    { "type": "bot_api_key",  "key": "..." }
    { "type": "pong"         }
"""

import asyncio
import json
import logging
import time
from typing import Optional

from aiohttp import web, WSMsgType

log = logging.getLogger('session')


class DeviceSession:
    def __init__(self, device_id: str, ws: web.WebSocketResponse, client_ip: str):
        self.device_id  = device_id
        self.ws         = ws
        self.client_ip  = client_ip
        self.connected_at = time.time()
        self.last_seen  = time.time()

        # Lazy import чтобы не тащить зависимости при загрузке модуля
        try:
            from core.backend import SessionBackend
        except ImportError:
            from backend import SessionBackend
        self.backend = SessionBackend()

        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._running = True

    # ── Основной цикл ─────────────────────────────────────────────────────────

    async def run(self):
        """Запускает recv и send loop параллельно."""
        await asyncio.gather(
            self._recv_loop(),
            self._send_loop(),
        )

    async def _recv_loop(self):
        async for msg in self.ws:
            self.last_seen = time.time()

            if msg.type == WSMsgType.TEXT:
                await self._handle_message(msg.data)

            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break

        self._running = False
        self._send_queue.put_nowait(None)  # Разблокируем send loop

    async def _send_loop(self):
        while self._running:
            try:
                item = await asyncio.wait_for(self._send_queue.get(), timeout=1.0)
                if item is None:
                    break
                if not self.ws.closed:
                    await self.ws.send_str(item)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error(f'[{self.device_id}] Send error: {e}')
                break

    # ── Обработка входящих сообщений ──────────────────────────────────────────

    async def _handle_message(self, raw: str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            log.warning(f'[{self.device_id}] Invalid JSON: {raw[:100]}')
            return

        msg_type = payload.get('type')

        if msg_type == 'ping':
            await self._send({'type': 'pong'})

        elif msg_type == 'ws_message':
            await self._on_ws_message(payload)

        elif msg_type == 'auth':
            await self._on_auth(payload)

        elif msg_type == 'command':
            await self._on_command(payload)

        elif msg_type == 'predict_req':
            await self._on_predict()

        elif msg_type == 'log':
            # Лог от агента — просто выводим на сервере
            log.info(f'[{self.device_id}] Agent: {payload.get("message", "")}')

        elif msg_type == 'request_bot_key':
            await self._on_request_bot_key()

        else:
            log.debug(f'[{self.device_id}] Unknown message type: {msg_type}')

    # ── Обработчики ───────────────────────────────────────────────────────────

    async def _on_ws_message(self, payload: dict):
        direction  = payload.get('direction', 'UNKNOWN')
        data       = payload.get('data', '')
        data_type  = payload.get('dataType', 'String')

        if data_type != 'String' or not isinstance(data, str):
            return

        # Обрабатываем в executor чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self.backend.process_ws, direction, data)
        except Exception as e:
            log.error(f'[{self.device_id}] Backend process_ws error: {e}')
            return

        # После обработки пушим обновление UI на телефон
        await self._push_view_data()

    async def _on_auth(self, payload: dict):
        bearer = payload.get('bearer')
        cfjwt  = payload.get('cfjwt')
        if bearer or cfjwt:
            self.backend.set_auth(bearer, cfjwt)
            log.info(f'[{self.device_id}] Auth tokens received (***{(bearer or "")[-8:]})')

            # Отправляем bot api key если есть
            await self._on_request_bot_key()

    async def _on_command(self, payload: dict):
        cmd = payload.get('data', '') or payload.get('text', '')
        if not cmd:
            return

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, self.backend.process_command, cmd)
            error_msg = result if isinstance(result, str) else None
        except Exception as e:
            error_msg = str(e)

        await self._push_view_data()
        if error_msg:
            await self._send({'type': 'error', 'message': error_msg})

    async def _on_predict(self):
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, self.backend.predict)
            await self._send({'type': 'predict', 'result': result})
        except Exception as e:
            await self._send({'type': 'predict', 'result': f'Predict error: {e}'})

    async def _on_request_bot_key(self):
        key = self.backend.get_bot_api_key()
        if key:
            await self._send({'type': 'bot_api_key', 'key': key})

    # ── Отправка view_data ────────────────────────────────────────────────────

    async def _push_view_data(self):
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, self.backend.build_view_data)
            await self._send({'type': 'view_data', 'payload': data})
        except Exception as e:
            log.error(f'[{self.device_id}] build_view_data error: {e}')

    # ── Утилиты ───────────────────────────────────────────────────────────────

    async def _send(self, obj: dict):
        if not self.ws.closed:
            try:
                self._send_queue.put_nowait(json.dumps(obj, ensure_ascii=False))
            except asyncio.QueueFull:
                log.warning(f'[{self.device_id}] Send queue full, dropping message')

    def info(self) -> dict:
        return {
            'device_id':    self.device_id,
            'client_ip':    self.client_ip,
            'connected_at': self.connected_at,
            'last_seen':    self.last_seen,
            'uptime':       int(time.time() - self.connected_at)
        }
