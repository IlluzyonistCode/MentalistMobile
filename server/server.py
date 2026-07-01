"""
Mentalist Server — центральный WebSocket сервер.

Принимает подключения от телефонов (production)
и от debug-клиента (ADB режим).

Endpoints:
  ws://host:port/device   — подключение APK
  http://host:port/agent  — скачать agent.js
  http://host:port/health — статус сервера
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Гарантируем что запуск из любой папки найдёт core/
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from aiohttp import web
import aiohttp

from core.device_manager import DeviceManager
from core.auth import IPWhitelist
from core.session import DeviceSession

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('MentalistServer')

# ── Конфиг ────────────────────────────────────────────────────────────────────

SERVER_HOST      = os.environ.get('SERVER_HOST',      '0.0.0.0')
SERVER_PORT      = int(os.environ.get('SERVER_PORT',  8765))
AGENT_JS_PATH    = os.environ.get('AGENT_JS_PATH',    str(Path(__file__).parent.parent / 'agent.js'))
WHITELIST_PATH   = os.environ.get('WHITELIST_PATH',   str(Path(__file__).parent / 'whitelist.txt'))
MAX_DEVICES      = int(os.environ.get('MAX_DEVICES',  50))

device_manager = DeviceManager(max_devices=MAX_DEVICES)
whitelist      = IPWhitelist(WHITELIST_PATH)


# ── WebSocket handler (/device) ────────────────────────────────────────────────

async def handle_device(request: web.Request) -> web.WebSocketResponse:
    """
    Каждый телефон подключается сюда.
    Создаётся DeviceSession — изолированный контекст с Tracker + Mastermind.
    """
    client_ip = _get_client_ip(request)

    if not whitelist.is_allowed(client_ip):
        log.warning(f'Rejected connection from {client_ip} — not in whitelist')
        raise web.HTTPForbidden(reason='IP not in whitelist')

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    device_id = f'{client_ip}:{int(time.time()*1000)}'
    session   = DeviceSession(device_id=device_id, ws=ws, client_ip=client_ip)

    if not device_manager.add(session):
        log.warning(f'Rejected {client_ip} — device limit reached ({MAX_DEVICES})')
        await ws.close(code=1013, message=b'Server full')
        return ws

    log.info(f'Device connected: {device_id}')

    try:
        await session.run()
    except Exception as e:
        log.error(f'Session error [{device_id}]: {e}', exc_info=True)
    finally:
        device_manager.remove(device_id)
        log.info(f'Device disconnected: {device_id}')

    return ws


# ── HTTP: отдача agent.js (/agent) ────────────────────────────────────────────

async def handle_agent(request: web.Request) -> web.Response:
    """
    Телефон при старте скачивает agent.js отсюда.
    Проверяем IP перед отдачей.
    """
    client_ip = _get_client_ip(request)

    if not whitelist.is_allowed(client_ip):
        log.warning(f'Agent download rejected: {client_ip}')
        raise web.HTTPForbidden(reason='IP not in whitelist')

    try:
        agent_path = Path(AGENT_JS_PATH)
        if not agent_path.exists():
            log.error(f'agent.js not found at {AGENT_JS_PATH}')
            raise web.HTTPNotFound(reason='agent.js not found on server')

        content = agent_path.read_text(encoding='utf-8')
        log.info(f'agent.js served to {client_ip} ({len(content)} bytes)')

        return web.Response(
            text=content,
            content_type='application/javascript',
            headers={
                'Cache-Control': 'no-store',
                'X-Mentalist-Version': '2.0'
            }
        )
    except web.HTTPException:
        raise
    except Exception as e:
        log.error(f'Error serving agent: {e}')
        raise web.HTTPInternalServerError()


# ── HTTP: статус (/health) ─────────────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({
        'status':       'ok',
        'devices':      device_manager.count(),
        'max_devices':  MAX_DEVICES,
        'uptime':       int(time.time() - _start_time)
    })


# ── HTTP: список устройств (/admin/devices) ───────────────────────────────────

async def handle_admin_devices(request: web.Request) -> web.Response:
    """Простой admin endpoint — список активных сессий."""
    admin_key = os.environ.get('ADMIN_KEY', '')
    if admin_key and request.headers.get('X-Admin-Key') != admin_key:
        raise web.HTTPUnauthorized()

    devices = device_manager.list_devices()
    return web.json_response({'devices': devices})


# ── HTTP: добавить IP в whitelist (/admin/whitelist) ──────────────────────────

async def handle_whitelist_add(request: web.Request) -> web.Response:
    admin_key = os.environ.get('ADMIN_KEY', '')
    if admin_key and request.headers.get('X-Admin-Key') != admin_key:
        raise web.HTTPUnauthorized()

    try:
        body = await request.json()
        ip   = body.get('ip', '').strip()
        if not ip:
            return web.json_response({'error': 'ip required'}, status=400)

        whitelist.add(ip)
        log.info(f'Whitelist: added {ip}')
        return web.json_response({'ok': True, 'ip': ip})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=400)


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _get_client_ip(request: web.Request) -> str:
    """Достаём реальный IP с учётом прокси."""
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote


_start_time = time.time()


# ── Точка входа ───────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get('/device',          handle_device)
    app.router.add_get('/agent',           handle_agent)
    app.router.add_get('/health',          handle_health)
    app.router.add_get('/admin/devices',   handle_admin_devices)
    app.router.add_post('/admin/whitelist', handle_whitelist_add)
    return app


def main():
    log.info(f'Starting Mentalist Server on {SERVER_HOST}:{SERVER_PORT}')
    log.info(f'agent.js path: {AGENT_JS_PATH}')
    log.info(f'Whitelist: {WHITELIST_PATH}')
    log.info(f'Max devices: {MAX_DEVICES}')

    app = create_app()
    web.run_app(app, host=SERVER_HOST, port=SERVER_PORT, access_log=None)


if __name__ == '__main__':
    main()
