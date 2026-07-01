import threading
import os
from pathlib import Path
from dotenv import load_dotenv

# Ищем config.txt в корне проекта (server/../config.txt),
# чтобы скрипт работал независимо от текущей рабочей директории
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / 'config.txt', override=False)

PACKAGE_NAME   = os.environ.get('PACKAGE_NAME',   'com.mentalist.mobile')
JS_SCRIPT_PATH = os.environ.get('JS_SCRIPT_PATH', str(_ROOT / 'agent.js'))
DEVICE_SERIAL  = os.environ.get('DEVICE_SERIAL',  None)

SERVER_URL     = os.environ.get('MENTALIST_SERVER_URL',     'http://localhost:1101')
SERVER_API_KEY = os.environ.get('MENTALIST_SERVER_API_KEY', '')


script            = None
session           = None
backend           = None
auth_client       = None


shutdown_event = threading.Event()