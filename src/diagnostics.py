"""Diagnóstico local sin dependencias gráficas ni llamadas a servicios externos."""
import http.client
import json
import logging
import re
import sqlite3
from contextlib import closing
from collections import deque
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_env(root=ROOT):
    path = Path(root) / '.env'
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.*)$', line)
        if match:
            value = match[2].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            result[match[1]] = value
    return result


def redact(text, secrets=()):
    text = str(text)
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[OCULTO]')
    text = re.sub(r'\b(?:cfk|cfut|cfat)_[A-Za-z0-9_-]+', '[OCULTO]', text)
    text = re.sub(r'\b\d{6,}:[A-Za-z0-9_-]{20,}', '[OCULTO]', text)
    return re.sub(r'(?i)(Bearer\s+)\S+', r'\1[OCULTO]', text)


def secret_values(root=ROOT):
    return [value for name, value in read_env(root).items()
            if any(part in name.upper() for part in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY'))]


class SafeLogFormatter(logging.Formatter):
    def __init__(self, secrets):
        super().__init__('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        self.secrets = secrets

    def format(self, record):
        return redact(super().format(record), self.secrets)


def install_file_logging(root=ROOT):
    path = Path(root) / 'logs' / 'app.log'
    logger = logging.getLogger()
    if any(getattr(h, 'baseFilename', None) == str(path.resolve()) for h in logger.handlers):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding='utf-8')
    handler.setFormatter(SafeLogFormatter(secret_values(root)))
    logger.addHandler(handler)


def status(root=ROOT):
    root = Path(root)
    env = read_env(root)
    token = env.get('CLOUDFLARE_API_TOKEN', '')
    findings = []
    if not env:
        findings.append('No se encontró configuración .env.')
    if token.startswith('cfk_'):
        findings.append('La clave global está en el campo API_TOKEN. Requiere correo de Cloudflare y autenticación X-Auth-Key/X-Auth-Email.')
    result = {
        'env_exists': (root / '.env').is_file(),
        'configured': {name: bool(env.get(name)) for name in (
            'TELEGRAM_BOT_TOKEN', 'GOOGLE_API_KEY', 'CLOUDFLARE_ACCOUNT_ID',
            'CLOUDFLARE_D1_DATABASE_ID', 'CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_EMAIL')},
        'credential_type': 'global_api_key' if token.startswith('cfk_') else 'api_token' if token else 'missing',
        'cloud_auth_verified': False,
        'local_database': {'exists': False}, 'worker': None, 'findings': findings,
        'app_log_exists': (root / 'logs' / 'app.log').is_file(),
    }
    database = root / 'database' / 'expenses.db'
    if database.is_file():
        try:
            with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                count, last = db.execute('SELECT COUNT(*), MAX(date) FROM expenses').fetchone()
            result['local_database'] = {'exists': True, 'count': count, 'last_expense_date': last}
        except sqlite3.Error:
            result['local_database'] = {'exists': True, 'error': 'No se pudo leer la copia local.'}
    worker_file = root / 'database' / 'bolsa_worker_status.json'
    if worker_file.is_file():
        try:
            worker = json.loads(worker_file.read_text(encoding='utf-8'))
            result['worker'] = {key: worker.get(key) for key in ('status', 'pid', 'heartbeat_utc')}
            heartbeat = datetime.fromisoformat(worker['heartbeat_utc'].replace('Z', '+00:00'))
            result['worker']['heartbeat_age_seconds'] = max(0, int((datetime.now(timezone.utc) - heartbeat).total_seconds()))
        except (ValueError, KeyError, TypeError):
            result['findings'].append('El estado del worker no es válido.')
    return result


def web_status(port=5050):
    result = {}
    for route in ('/dashboard', '/transactions', '/details'):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=12)
        try:
            connection.request('GET', route)
            response = connection.getresponse()
            body = response.read(8192).decode('utf-8', errors='replace')
            title = re.search(r'<title>(.*?)</title>', body, re.I | re.S)
            result[route] = {'http_status': response.status, 'title': title[1] if title else None,
                             'data_source': response.getheader('X-Data-Source', 'primary')}
        except (OSError, http.client.HTTPException):
            result[route] = {'http_status': None, 'error': 'El servidor local no respondió.'}
        finally:
            connection.close()
    return result


def recent_errors(root=ROOT, lines=30):
    result = {}
    secrets = secret_values(root)
    for name in ('logs/app.log', 'database/bolsa_worker.log'):
        path = Path(root) / name
        if not path.is_file():
            result[name] = {'exists': False, 'entries': []}
            continue
        with path.open(encoding='utf-8', errors='replace') as stream:
            entries = deque((redact(line.rstrip(), secrets)[:2000] for line in stream
                             if any(level in line.upper() for level in ('ERROR', 'WARNING', 'TRACEBACK', 'EXCEPTION'))), maxlen=lines)
        result[name] = {'exists': True, 'entries': list(entries)}
    return result
