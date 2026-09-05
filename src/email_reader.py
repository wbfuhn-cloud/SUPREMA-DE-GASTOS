"""
email_reader.py -- Lector automatico de correos Banco Azteca (BAZ Digital)
=========================================================================
Usa Microsoft Graph API con OAuth2.
La primera vez, el navegador se abrirá automáticamente para aprobar el acceso.
El token se guarda en .token_cache.json y se renueva automaticamente.
"""

import os
import sys
import re
import logging
import sqlite3
from datetime import datetime

# -- Path setup -------------------------------------------------------
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv # type: ignore
load_dotenv(os.path.join(project_root, '.env'))

try:
    import msal # type: ignore
    import requests as http_requests # type: ignore
except ImportError as e:
    logging.error(f"[ERROR] Dependencia faltante en email_reader: {e}. Ejecuta: pip install msal requests")
    msal = None
    http_requests = None

from src.database import DatabaseManager # type: ignore
from src.analyzer import AnalysisService # type: ignore
from src.core.constants import MONTHS_ES_MAP

# -- Logging ----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('EmailReader')

# -- Configuracion desde .env -----------------------------------------
EMAIL_ADDRESS    = os.getenv('EMAIL_ADDRESS', '')
SENDER_FILTER_RAW = os.getenv('EMAIL_SENDER_FILTER', 'notificaciones@bazdigital.com')
SENDER_FILTERS    = [s.strip() for s in SENDER_FILTER_RAW.split(',')]
TOKEN_CACHE_PATH = os.path.join(project_root, 'data', '.token_cache.json')

# Thunderbird public Client ID app que soporta cuentas personales Microsoft
CLIENT_ID  = '9e5f94bc-e8a4-4e73-b8be-63364c29d753'
AUTHORITY  = 'https://login.microsoftonline.com/consumers'
SCOPES     = ['https://graph.microsoft.com/Mail.Read',
              'https://graph.microsoft.com/Mail.ReadWrite']

GRAPH_BASE = 'https://graph.microsoft.com/v1.0'

# -- Mapa de categorias -----------------------------------------------
CATEGORY_MAP = {
    'OXXO': 'COMIDA', 'WALMART': 'COMIDA', 'SUPER': 'COMIDA',
    'SORIANA': 'COMIDA', 'CHEDRAUI': 'COMIDA', 'BODEGA': 'COMIDA',
    'SAMS': 'COMIDA', 'COSTCO': 'COMIDA', 'DOMINOS': 'COMIDA',
    'MC DONALDS': 'COMIDA', 'MCDONALDS': 'COMIDA', 'BURGER': 'COMIDA',
    'KFC': 'COMIDA', 'PIZZA': 'COMIDA', 'SUBWAY': 'COMIDA',
    'STARBUCKS': 'COMIDA', 'UBER EATS': 'COMIDA', 'RAPPI': 'COMIDA',
    'GASOLINERA': 'TRANSPORTE', 'PEMEX': 'TRANSPORTE', 'UBER': 'TRANSPORTE',
    'DIDI': 'TRANSPORTE', 'CABIFY': 'TRANSPORTE',
    'CINEMA': 'ENTRETENIMIENTO', 'CINEPOLIS': 'ENTRETENIMIENTO',
    'CINEMEX': 'ENTRETENIMIENTO', 'NETFLIX': 'ENTRETENIMIENTO',
    'SPOTIFY': 'ENTRETENIMIENTO', 'AMAZON': 'SERVICIOS',
    'CFE': 'SERVICIOS', 'TELMEX': 'SERVICIOS', 'TELCEL': 'SERVICIOS',
    'IZZI': 'SERVICIOS', 'FARMACIA': 'SALUD', 'HOSPITAL': 'SALUD',
}

def guess_category(merchant):
    m = merchant.upper()
    for kw, cat in CATEGORY_MAP.items():
        if kw in m:
            return cat
    return 'OTRO'

# -- Patrones regex para correos BAZ ----------------------------------
PATTERNS = [
    {
        'regex': r'(?:compra|compraste|cargo|pago)[^\$]{0,30}\$\s*([\d,]+\.?\d*).*?Comercio:\s*([A-Z0-9][^\n\r<]{1,50}?)(?=\s+(?:Tarjeta|Autorizaci|Estatus|Comisi)|$)',
        'type': 'compra'
    },
    {
        'regex': r'(?:compra|cargo|pago)[^\$]{0,30}\$\s*([\d,]+\.?\d*)\s*(?:MXN)?\s*(?:en|con|a)\s+([A-Z0-9][^\n\r<]{1,50})',
        'type': 'compra'
    },
    {
        'regex': r'\$\s*([\d,]+\.?\d*)\s*(?:MXN)?\s+en\s+([A-Z0-9][^\n\r<]{1,50})',
        'type': 'compra'
    },
    {
        'regex': r'(?:retiro|retiraste)[^\$]{0,30}\$\s*([\d,]+\.?\d*)',
        'type': 'retiro'
    },
    {
        'regex': r'(?:transferencia|enviaste|transferiste)[^\$]{0,30}\$\s*([\d,]+\.?\d*)\s*(?:MXN)?\s*(?:a\s+)?([A-Z0-9][^\n\r<]{1,50})?',
        'type': 'transferencia'
    },
    {
        'regex': r'\$\s*([\d,]+\.\d{2})',
        'type': 'gasto'
    },
]

def parse_email_body(body):
    """Extrae monto, comercio y tipo de operacion del cuerpo del correo."""
    if not body: return None
    clean = re.sub(r'<[^>]+>', ' ', body)
    clean = re.sub(r'\s+', ' ', clean)

    for pat in PATTERNS:
        match = re.search(pat['regex'], clean, re.IGNORECASE)
        if not match: continue
        groups = match.groups()
        amount_str = groups[0].replace(',', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        if amount <= 0: continue
        merchant = 'BAZ DIGITAL'
        if len(groups) >= 2 and groups[1]:
            merchant = re.sub(r'[^\w\s]$', '', groups[1]).strip()
            # Truncar a 50 caracteres
            merchant = merchant[:50].upper()
        return {'amount': amount, 'merchant': merchant, 'op_type': str(pat['type'])}
    return None

def send_telegram_notification(text):
    """Envía una notificación simple a Telegram."""
    from src.infra.telegram_utils import send_telegram_message
    send_telegram_message(text)

class TokenManager:
    """Maneja el token OAuth2 de Microsoft con cache persistente usando navegador interactivo."""

    def __init__(self):
        self._cache = msal.SerializableTokenCache()
        if os.path.exists(TOKEN_CACHE_PATH):
            with open(TOKEN_CACHE_PATH, 'r') as f:
                self._cache.deserialize(f.read())

        self._app = msal.PublicClientApplication(
            client_id=CLIENT_ID,
            authority=AUTHORITY,
            token_cache=self._cache,
        )

    def _save_cache(self):
        if self._cache.has_state_changed:
            with open(TOKEN_CACHE_PATH, 'w') as f:
                f.write(self._cache.serialize())

    def get_token(self):
        """Obtiene token. Si no hay cache vÃ¡lida, abre el navegador local."""
        accounts = self._app.get_accounts()

        if accounts:
            result = self._app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and 'access_token' in result:
                self._save_cache()
                return result['access_token']

        # No hay token silente -> Interactive Browser Flow
        log.info("Autorizacion requerida. Abriendo una pestaña en tu navegador...")
        print("\n=======================================================")
        print(" Se esta abriendo una pestana en tu navegador web...")
        print(" Por favor inicia sesion con tu cuenta de Outlook y acepta.")
        print(" (No cierres esta ventana negra mientras tanto)")
        print("=======================================================\n")
        
        # Iniciar navegador automaticamente (MSAL levanta un localhost temporal)
        result = self._app.acquire_token_interactive(scopes=SCOPES)

        if result and 'access_token' in result:
            self._save_cache()
            log.info("[OK] Autorizacion MSAL exitosa. Token guardado en cache.")
            return result['access_token']
        else:
            log.error(f"Error Oauth2: {result.get('error_description', result.get('error'))}")
            return None

class EmailReader:
    """Lee correos de BAZ Digital via Microsoft Graph API y los registra en la BD."""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.token_mgr = TokenManager()
        self.analyzer = None
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            try:
                self.analyzer = AnalysisService(api_key)
            except: pass
        self._ensure_email_log_table()

    def _ensure_email_log_table(self):
        self.db.ensure_email_log_table()

    def _is_already_processed(self, message_id):
        return self.db.is_email_processed(message_id)

    def _log_email(self, message_id, subject, received_at, expense_id, amount, merchant, status):
        self.db.log_email(message_id, subject, received_at, expense_id, amount, merchant, status)

    def _graph_get(self, token, url, params=None):
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        try:
            resp = http_requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            log.error(f"Graph API error {resp.status_code}: {resp.text[:300]}")
        except http_requests.exceptions.RequestException as e:
            log.error(f"Graph API network error (_graph_get): {e}")
        return None

    def _graph_patch(self, token, url, body):
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        try:
            resp = http_requests.patch(url, headers=headers, json=body, timeout=30)
            return resp.status_code in (200, 204)
        except http_requests.exceptions.RequestException as e:
            log.error(f"Graph API network error (_graph_patch): {e}")
            return False

    def _fetch_baz_emails(self, token, unread_only=True, limit=20):
        """Obtiene correos de BAZ Digital y otros bancos via Graph API."""
        # Si hay múltiples filtros, obtenemos los más recientes y filtramos en Python
        # para evitar errores de OData en Graph API.
        params = {
            '$select': 'id,subject,receivedDateTime,body,isRead,from',
            '$top': limit * 2, # Pedimos más para filtrar
        }

        data = self._graph_get(token, f'{GRAPH_BASE}/me/messages', params=params)
        if not data:
            return []
            
        messages = data.get('value', [])
        
        # Filtramos por remitente y estado 'isRead'
        filtered = []
        for m in messages:
            sender = m.get('from', {}).get('emailAddress', {}).get('address', '').lower()
            if any(f.lower() in sender for f in SENDER_FILTERS):
                if not unread_only or str(m.get('isRead')).lower() == 'false':
                    filtered.append(m)
            
        return filtered[:limit]

    def _mark_as_read(self, token, msg_id):
        url = f'{GRAPH_BASE}/me/messages/{msg_id}'
        self._graph_patch(token, url, {'isRead': True})

    def run_once(self, test_mode=False):
        """Obtiene token, procesa correos y retorna cantidad importada."""
        token = self.token_mgr.get_token()
        if not token:
            log.error("No se pudo obtener token de acceso. Abortando.")
            return 0

        emails = self._fetch_baz_emails(
            token,
            unread_only=not test_mode,
            limit=10 if test_mode else 50
        )

        if not emails:
            log.info("No hay correos nuevos de BAZ Digital.")
            return 0
        
        log.info(f"Correos encontrados: {len(emails)}")
        imported = 0

        for msg in emails:
            msg_id      = msg.get('id', '')
            subject     = msg.get('subject', '(sin asunto)')
            received_at = msg.get('receivedDateTime', '')
            body_html   = msg.get('body', {}).get('content', '')

            log.info(f"Procesando: [{subject}]")

            if not test_mode and self._is_already_processed(msg_id):
                log.info("   Ya procesado. Saltando.")
                continue

            # Primero intentamos con Regex (rápido y gratis)
            parsed = parse_email_body(body_html)
            
            # Si falla y tenemos Gemini, intentamos con IA
            if not parsed and self.analyzer:
                log.info("   Regex no detecto nada. Intentando con Gemini AI...")
                # Limpiar HTML antes de enviar a Gemini
                clean_body = re.sub(r'<[^>]+>', ' ', body_html)
                clean_body = re.sub(r'\s+', ' ', clean_body).strip()
                
                ai_data = self.analyzer.analyze_email_body(clean_body)
                if ai_data and ai_data.get('total'):
                    parsed = {
                        'amount': float(ai_data['total']),
                        'merchant': ai_data.get('merchant', 'DESCONOCIDO'),
                        'op_type': ai_data.get('type', 'gasto'),
                        'details_ai': ai_data.get('details', '')
                    }
                    log.info(f"   [IA] Detectado: ${parsed['amount']} en {parsed['merchant']}")

            if test_mode:
                if parsed:
                    log.info(f"   [TEST] Monto    : ${parsed['amount']:.2f}")
                    log.info(f"   [TEST] Comercio : {parsed['merchant']}")
                    log.info(f"   [TEST] Tipo     : {parsed['op_type']}")
                else:
                    log.warning("   [TEST] No se extrajeron datos validos.")
                continue

            if not parsed:
                self._log_email(msg_id, subject, received_at, None, None, None, 'skipped')
                continue

            amount   = parsed['amount']
            merchant = parsed['merchant']
            op_type  = parsed['op_type']

            try:
                dt = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
            except Exception:
                dt = datetime.now()

            category = guess_category(merchant)
            saved_cat, _ = self.db.get_most_frequent_category(merchant)
            if saved_cat: category = saved_cat

            expense_data = {
                'day':            dt.day,
                'month':          MONTHS_ES_MAP.get(dt.month, 'OTRO'),
                'week':           dt.isocalendar()[1],
                'date':           dt.strftime('%Y-%m-%d'),
                'payment_method': 'TARJETA BAZ',
                'category':       category,
                'merchant':       merchant,
                'subcategory':    '',
                'details':        f'AUTO-BAZ: {str(op_type).upper()}',
                'total':          amount,
                'type':           'Normal',
                'status':         'unconfirmed',
            }

            ok, msg_res = self.db.add_expense(expense_data)

            if ok:
                id_match   = re.search(r'ID:\s*(\d+)', msg_res)
                expense_id = int(id_match.group(1)) if id_match else None
                self._log_email(msg_id, subject, received_at, expense_id, amount, merchant, 'imported')
                self._mark_as_read(token, msg_id)
                log.info(f"   [OK] ${amount:.2f} en {merchant} [{category}]")
                
                # Notificación a Telegram
                send_telegram_notification(
                    f"📧 **Nuevo Gasto Detectado (Email)**\n\n"
                    f"💰 **Monto**: ${amount:,.2f}\n"
                    f"🏪 **Comercio**: {merchant}\n"
                    f"📂 **Categoría**: {category}\n\n"
                    f"🔎 *Revisa y confirma este gasto en el dashboard o /transactions.*"
                )
                
                imported += 1
            else:
                self._log_email(msg_id, subject, received_at, None, amount, merchant, 'error')
                log.error(f"   [ERROR] {msg_res}")

        log.info(f"Total importados: {imported}")
        return imported

# -- CLI --------------------------------------------------------------
if __name__ == '__main__':
    authorize_mode = '--authorize' in sys.argv
    test_mode = '--test' in sys.argv

    if authorize_mode:
        print("=" * 62)
        print("  AUTORIZACION WEB DE CORREO (OAuth2) BAZ DIGITAL")
        print("=" * 62)
        if os.path.exists(TOKEN_CACHE_PATH):
            os.remove(TOKEN_CACHE_PATH)
        mgr = TokenManager()
        token = mgr.get_token()
        if token:
            print("\n[OK] Acceso guardado permanentemente. Ya puedes usar start.bat")
        else:
            print("\n[ERROR] Autorizacion fallida o cancelada.")
        sys.exit(0)

    print("=" * 62)
    if test_mode:
        print("  MODO TEST -- No se guardaran datos en la BD")
    else:
        print("  LECTOR BAZ DIGITAL (Graph API MSAL)")
    print("=" * 62)

    reader = EmailReader()
    n = reader.run_once(test_mode=test_mode)

    if not test_mode:
        print(f"\n[OK] Importacion completada: {n} gasto(s) registrado(s).")
