from flask import Flask, jsonify, request, make_response, send_file, send_from_directory, render_template, g
from flask_cors import CORS  # type: ignore
from werkzeug.exceptions import HTTPException
import sys
import os
import logging
from datetime import datetime, timezone
import threading
import time as _time
import json
import calendar
from pathlib import Path

# ─── Path ────────────────────────────────────────────────────────────────────
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.database import DatabaseManager
from src.dashboard import DashboardGenerator
from src.transactions_view import TransactionsViewGenerator
from src.details_view import DetailsViewGenerator
from src.excel_export import ExcelExporter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Managers ────────────────────────────────────────────────────────────────
db_manager = DatabaseManager()
visor_import_error: str | None = None

sys.path.append(os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT'))
from production_controls import (KillSwitch, OperationalMetrics, RateLimiter,
                                 authorized_write, correlation_id)
from release_governance import current_project_gate
from maturity_status import build_maturity_status
from auto_scan_schedule import auto_scan_due, next_nyse_open, nyse_market_is_open
from error_taxonomy import ERROR_CATEGORIES, ErrorRegistry, sanitize_public_error
from notification_config import resolve_telegram_chat_id
fetch_stock_data = process_single_ticker = None
get_cache_stats = clear_cache = get_ticker_cache_stats = clear_ticker_cache = None
calculate_position_size = analyze_portfolio = None
get_learner = get_ml_predictor = None
config_mgr = None
paper_ledger = paper_protocol = phase9_approval_fn = None
signal_explanation_fn = adaptive_ai_status_fn = filter_history_fn = None
_visor_loaded = False
_visor_lock = threading.Lock()


def _ensure_visor_loaded():
    """Carga pandas/sklearn y el motor bursátil solo cuando se usa Bolsa."""
    global _visor_loaded, visor_import_error, fetch_stock_data, process_single_ticker
    global get_cache_stats, clear_cache, get_ticker_cache_stats, clear_ticker_cache
    global calculate_position_size, analyze_portfolio, get_learner, get_ml_predictor, config_mgr
    global paper_ledger, paper_protocol, phase9_approval_fn
    global signal_explanation_fn, adaptive_ai_status_fn, filter_history_fn
    if _visor_loaded:
        return
    with _visor_lock:
        if _visor_loaded:
            return
        try:
            from stock_scanner import fetch_stock_data as _fetch, get_cache_stats as _stats, clear_cache as _clear, get_ticker_cache_stats as _ticker_stats, clear_ticker_cache as _ticker_clear, process_single_ticker as _process  # type: ignore
            from risk_calculator import calculate_position_size as _position  # type: ignore
            from config_manager import ConfigManager  # type: ignore
            from portfolio_analyzer import analyze_portfolio as _analyze  # type: ignore
            from recommendation_learner import get_learner as _learner  # type: ignore
            from ml_predictor import get_ml_predictor as _predictor  # type: ignore
            from paper_trading import PaperTradingLedger, freeze_protocol, phase9_approval as _phase9_approval  # type: ignore
            from signal_fusion import FUSION_VERSION  # type: ignore
            from technical_engine import HEURISTIC_VERSION  # type: ignore
            from explainability import signal_explanation, adaptive_ai_status, filter_history  # type: ignore
            fetch_stock_data, process_single_ticker = _fetch, _process
            get_cache_stats, clear_cache = _stats, _clear
            get_ticker_cache_stats, clear_ticker_cache = _ticker_stats, _ticker_clear
            calculate_position_size, analyze_portfolio = _position, _analyze
            get_learner, get_ml_predictor = _learner, _predictor
            config_mgr = ConfigManager()
            paper_protocol = freeze_protocol({
                'fusion_version': FUSION_VERSION,
                'heuristic_version': HEURISTIC_VERSION,
                'ml_policy': 'experiment_only',
                'fourier_policy': 'experiment_only',
                'minimum_data_quality': 0.95,
                'buy_probability_threshold': 0.65,
                'risk_per_trade_max': 0.01,
            })
            paper_ledger = PaperTradingLedger(os.path.join(root_dir, 'database', 'paper_trading.db'))
            phase9_approval_fn = _phase9_approval
            signal_explanation_fn = signal_explanation
            adaptive_ai_status_fn = adaptive_ai_status
            filter_history_fn = filter_history
            visor_import_error = None
        except ImportError as exc:
            visor_import_error = str(exc)
            logger.error(f"Error importando módulos de VISOR: {exc}")
        finally:
            _visor_loaded = True

# ─── Flask ───────────────────────────────────────────────────────────────────
app = Flask(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
CORS(app)
operations_metrics = OperationalMetrics()
api_rate_limiter = RateLimiter(limit=int(os.getenv('BOLSA_RATE_LIMIT', '120')), window_seconds=60)
operations_kill_switch = KillSwitch(Path(root_dir) / 'database' / 'kill_switch.json')
application_errors = ErrorRegistry(max_items=200)
WRITE_PATHS = ('/api/portfolio', '/api/learner/feedback', '/api/ml/retrain',
               '/api/scan/start', '/api/bolsa/operations/kill-switch')


@app.before_request
def _operational_request_controls():
    g.request_started = _time.perf_counter()
    g.correlation_id = correlation_id(request.headers.get('X-Correlation-ID'))
    if request.path.startswith('/api/'):
        client = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        if not api_rate_limiter.allow(client):
            return jsonify({'status': 'error', 'message': 'Límite de solicitudes excedido',
                            'correlation_id': g.correlation_id}), 429
    if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.path.startswith(WRITE_PATHS):
        if not authorized_write(os.getenv('BOLSA_WRITE_TOKEN'), request.headers.get('Authorization'),
                                os.getenv('APP_ENV', 'development')):
            return jsonify({'status': 'error', 'message': 'No autorizado',
                            'correlation_id': g.correlation_id}), 401


@app.after_request
def _operational_response_headers(response):
    request_id = getattr(g, 'correlation_id', correlation_id())
    elapsed = (_time.perf_counter() - getattr(g, 'request_started', _time.perf_counter())) * 1000
    operations_metrics.observe(request.path, elapsed, response.status_code)
    response.headers['X-Correlation-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    logger.info(json.dumps({'event': 'http_request', 'correlation_id': request_id,
                            'method': request.method, 'path': request.path,
                            'status': response.status_code, 'latency_ms': round(elapsed, 2)}))
    return response


@app.errorhandler(Exception)
def _classify_unhandled_error(error):
    if isinstance(error, HTTPException):
        return error
    request_id = getattr(g, 'correlation_id', correlation_id())
    item = application_errors.record({
        'message': str(error), 'component': 'server', 'source': request.path,
        'status_code': 500, 'correlation_id': request_id,
    })
    logger.exception("Error no controlado [%s] %s", item['category'], request_id)
    if request.path.startswith('/api/'):
        return jsonify({'status': 'error', 'error': item['category'],
                        'message': 'Error interno controlado', 'correlation_id': request_id}), 500
    return _html_response(_error_page(f"Error interno · referencia {request_id}")), 500


@app.before_request
def _load_bolsa_dependencies_on_demand():
    bolsa_api_prefixes = ('/api/bolsa', '/api/scan', '/api/learner', '/api/ml',
                          '/api/cache', '/api/risk', '/api/portfolio', '/api/dashboard-updates')
    if request.path.startswith('/bolsa') or request.path.startswith(bolsa_api_prefixes):
        _ensure_visor_loaded()

@app.template_filter('format_currency')
def format_currency_filter(val, decimals=2):
    try:
        if val is None:
            return "0.00" if decimals == 2 else "0"
        val_float = float(val)
        if decimals == 0:
            return f"{val_float:,.0f}"
        return f"{val_float:,.2f}"
    except (ValueError, TypeError):
        return str(val)


# ─── Estado global del escaneo ───────────────────────────────────────────────
_scan_lock = threading.Lock()
SCAN_STATE: dict = {
    'is_scanning':    False,
    'progress':       0.0,
    'message':        'Listo para iniciar',
    'results':        [],
    'market_context': None,
    'exchange_rate':  20.5,
    'generated_at_utc': None,
    'stop_event':     threading.Event(),
}

AUTO_SCAN_STATE: dict = {
    'enabled': os.environ.get('ENABLE_BOLSA_AUTO_SCAN', '1').strip().lower() not in {'0', 'false', 'no'},
    'scheduler_active': False,
    'interval_minutes': max(5, int(os.environ.get('BOLSA_AUTO_SCAN_INTERVAL_MINUTES', '60'))),
    'last_started_utc': None,
}

SCAN_CACHE_FILE = os.path.join(root_dir, 'database', 'last_scan_results.json')

def _load_scan_persistence():
    """Carga el último escaneo guardado desde disco."""
    if os.path.exists(SCAN_CACHE_FILE):
        try:
            with open(SCAN_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                loaded_results = data.get('results', [])
                try:
                    from market_data import ensure_quote_contract
                    upgraded = []
                    for result in loaded_results:
                        quote = ensure_quote_contract(result)
                        upgraded.append({
                            **result,
                            'Quote': quote,
                            # Los resultados heredados no prueban si un cero era
                            # real o un valor faltante convertido silenciosamente.
                            'Fundamentals_Available': (
                                result.get('Fundamentals_Available') is True
                                and quote.get('provider') != 'legacy_unknown'
                            ),
                            'Data_Quality': quote.get('quality_score', 0.0),
                            'Data_Quality_Issues': quote.get('quality_issues', []),
                            'Signal_Eligible': not quote.get('is_stale', True) and quote.get('quality_score', 0.0) >= 0.95,
                        })
                    loaded_results = upgraded
                except Exception as exc:
                    logger.warning(f"No se pudo actualizar contrato de cotización: {exc}")
                SCAN_STATE['results'] = loaded_results
                SCAN_STATE['market_context'] = data.get('market_context')
                SCAN_STATE['generated_at_utc'] = data.get('generated_at_utc') or data.get('timestamp')
                SCAN_STATE['message'] = 'Resultados cargados (historial)'
        except Exception as e:
            logger.error(f"Error cargando persistencia de escaneo: {e}")

def _save_scan_persistence():
    """Guarda el escaneo actual a disco."""
    try:
        os.makedirs(os.path.dirname(SCAN_CACHE_FILE), exist_ok=True)
        with open(SCAN_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'results': SCAN_STATE['results'],
                'market_context': SCAN_STATE['market_context'],
                'data_contract_version': '3.0',
                'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }, f, indent=4)
    except Exception as e:
        logger.error(f"Error guardando persistencia de escaneo: {e}")

# Cargar la persistencia inmediatamente al iniciar el módulo
try:
    _load_scan_persistence()
except Exception as e:
    logger.error(f"Error cargando persistencia inicial de escaneo: {e}")


# ─── Auto-escaneo ────────────────────────────────────────────────────────────
def _is_market_hours(now: datetime) -> bool:
    """Retorna True durante la sesión NYSE, con zona horaria, DST y festivos."""
    return nyse_market_is_open(now)


def _run_scan_worker(use_cache: bool = True, max_workers: int = 15, source: str = 'all'):
    """
    Worker reutilizable para escaneos manuales y automáticos.
    Llamar siempre desde un hilo separado.
    """
    def _progress(message, value):
        SCAN_STATE['message'] = message
        SCAN_STATE['progress'] = value
        try:
            print(f"[Bolsa] [{int(value*100)}%] {message}")
        except UnicodeEncodeError:
            print(f"[Bolsa] [{int(value*100)}%] {message.encode('ascii', 'replace').decode('ascii')}")

    with _scan_lock:
        if SCAN_STATE['is_scanning']:
            return          # ya hay uno corriendo
        SCAN_STATE['is_scanning'] = True
        SCAN_STATE['stop_event'].clear()
        SCAN_STATE['progress'] = 0.0
        SCAN_STATE['message'] = 'Iniciando escaneo...'
        SCAN_STATE['results'] = []
        SCAN_STATE['market_context'] = None

    try:
        if not fetch_stock_data:
            raise RuntimeError(f"Motor de escaneo no disponible. Error: {visor_import_error}")

        # Obtener contexto de mercado antes del escaneo
        try:
            from stock_scanner import get_market_regime  # type: ignore
            market_ctx = get_market_regime()
            SCAN_STATE['market_context'] = market_ctx
        except Exception as e:
            logger.warning(f"No se pudo obtener contexto de mercado: {e}")

        data = fetch_stock_data(
            progress_callback=_progress,
            stop_event=SCAN_STATE['stop_event'],
            use_cache=use_cache,
            max_workers=max_workers,
            source=source,
        )

        if SCAN_STATE['stop_event'].is_set():
            SCAN_STATE['message'] = 'Escaneo Detenido'
        elif isinstance(data, list) or isinstance(data, dict):
            if isinstance(data, list):
                SCAN_STATE['results']  = data
                SCAN_STATE['message']  = f'[OK] Escaneo finalizado: {len(data)} oportunidades'
            else:
                SCAN_STATE['results']        = data.get('results', [])
                SCAN_STATE['market_context'] = data.get('market_context')
                SCAN_STATE['message']        = 'Escaneo Finalizado'
                
            SCAN_STATE['progress'] = 1.0
            SCAN_STATE['generated_at_utc'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            _save_scan_persistence()
            try:
                for result in SCAN_STATE['results']:
                    quote = result.get('Quote') or {}
                    for horizon_name, fusion in (result.get('Fusion_Horizons') or {}).items():
                        paper_ledger.append_signal({
                            'decision_hash': fusion.get('decision_hash'),
                            'ticker': result.get('Ticker'),
                            'signal': fusion.get('state'),
                            'horizon': horizon_name,
                            'quoted_price': result.get('Price'),
                            'data_timestamp_utc': quote.get('market_timestamp'),
                            'provider': quote.get('provider'),
                            'data_quality': result.get('Data_Quality', 0.0),
                            'baseline_signal': result.get('Signal_State'),
                            'candidate_signal': fusion.get('state'),
                            'model_version': result.get('Model_Version') or 'unavailable',
                            'rules_version': result.get('Fusion_Version') or 'unknown',
                            'emitted_at_utc': SCAN_STATE['generated_at_utc'],
                            'market_session': quote.get('session') or SCAN_STATE['generated_at_utc'][:10],
                        }, paper_protocol['configuration_hash'])
            except Exception as exc:
                logger.error(f"No se pudo registrar paper trading: {exc}", exc_info=True)
            
            # Enviar notificación a Telegram
            try:
                import os, requests
                from portfolio_analyzer import get_portfolio_summary
                summary_msg = get_portfolio_summary()
                
                results = SCAN_STATE['results']
                if results:
                    top_3 = sorted(results, key=lambda x: x.get('Score', 0), reverse=True)[:3]
                    gemas = ["\n💎 *GEMAS DEL DÍA (Oportunidades)*", "━━━━━━━━━━━━━━━━━━━━"]
                    for t in top_3:
                        nota = t.get('Nota', '')
                        nota_str = f" | {nota}" if nota else ""
                        gemas.append(f"⭐ *{t.get('Ticker')}* | Score: {t.get('Score')} ({t.get('Viabilidad')})")
                        gemas.append(f"   Precio: ${t.get('Price')}{nota_str}")
                    summary_msg += "\n\n" + "\n".join(gemas)
                
                token = os.getenv("TELEGRAM_BOT_TOKEN", "")
                chat_id = resolve_telegram_chat_id(
                    root_dir, token, os.getenv("TELEGRAM_CHAT_ID", "")
                )
                
                if token and chat_id:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": summary_msg, "parse_mode": "Markdown"},
                        timeout=10
                    )
            except Exception as e:
                logger.error(f"Error enviando notificacion bolsa: {e}", exc_info=True)
                
        else:
            SCAN_STATE['message'] = 'Sin resultados'

    except Exception as e:
        logger.error(f"Error en escaneo: {e}", exc_info=True)
        SCAN_STATE['message'] = f'Error: {e}'
    finally:
        SCAN_STATE['is_scanning'] = False


def run_auto_scan_loop():
    """Programador permanente; escanea sólo durante sesiones NYSE válidas."""
    AUTO_SCAN_STATE['scheduler_active'] = True
    logger.info("[AI] Hilo de auto-escaneo iniciado.")
    _time.sleep(30)   # respirar al inicio

    while True:
        try:
            now = datetime.now(timezone.utc)
            last_started = AUTO_SCAN_STATE.get('last_started_utc')
            if isinstance(last_started, str):
                last_started = datetime.fromisoformat(last_started.replace('Z', '+00:00'))
            due = auto_scan_due(now, last_started, AUTO_SCAN_STATE['interval_minutes'])
            if (AUTO_SCAN_STATE['enabled'] and due
                    and not SCAN_STATE['is_scanning'] and fetch_stock_data):
                logger.info("[SCAN] Ejecutando escaneo programado...")
                AUTO_SCAN_STATE['last_started_utc'] = now.isoformat().replace('+00:00', 'Z')
                threading.Thread(target=_run_scan_worker, daemon=True).start()
        except Exception as e:
            logger.error(f"Error en loop de auto-escaneo: {e}")

        _time.sleep(60)   # programador activo siempre; el intervalo evita duplicados


def run_prediction_recovery_loop():
    """Recupera resultados vencidos aunque no se ejecute un nuevo escaneo."""
    logger.info("[LEARN] Hilo de verificación de predicciones iniciado.")
    _time.sleep(45)
    while True:
        try:
            if get_learner:
                summary = get_learner().verify_past_recommendations()
                logger.info(f"[LEARN] Recuperación de resultados: {summary}")
        except Exception as exc:
            logger.error(f"Error en recuperación de predicciones: {exc}", exc_info=True)
        _time.sleep(6 * 3600)





def run_live_alert_loop():
    """Ejecuta un escaneo continuo de alertas en vivo para la bolsa."""
    logger.info("[BOLT] Hilo de alertas en vivo iniciado.")
    _time.sleep(15)  # respirar al inicio

    while True:
        interval = 5
        try:
            if not config_mgr:
                _time.sleep(60)
                continue
            
            cfg = config_mgr.config.get('live_alerts', {})
            if not cfg.get('enabled', False):
                _time.sleep(60)
                continue
                
            interval = cfg.get('interval_minutes', 5)
            # Default to 0.40 since our prompt requested smart alerts, scale is 0.0 to 1.0 here for min_confidence
            min_confidence = cfg.get('min_confidence', 40.0) / 100.0 
            sources = cfg.get('sources', ['trump', 'portfolio', 'watchlist'])
            
            if not get_learner or not process_single_ticker: # type: ignore
                _time.sleep(60)
                continue
                
            learner = get_learner()
            
            # Recolectar tickers
            tickers_to_check = set()
            from stock_scanner import get_tickers_by_source # type: ignore
            for src in sources:
                try:
                    if src == 'watchlist':
                        tickers_to_check.update(config_mgr.get_watchlist())
                    elif src == 'portfolio':
                        tickers_to_check.update(config_mgr.get_portfolio().keys())
                    else:
                        tickers_to_check.update(get_tickers_by_source(src))
                except Exception as e:
                    logger.error(f"Error obteniendo tickers para fuente {src}: {e}")
            
            for ticker in tickers_to_check:
                try:
                    r = process_single_ticker(ticker) # type: ignore
                    if not r:
                        continue
                        
                    # Evaluar acción
                    score = r.get('Score')
                    price = r.get('Price', 0.0)
                    viabilidad = r.get('Viabilidad', '')
                    signal_state = r.get('Signal_State', 'SIN SEÑAL')
                    signal_eligible = r.get('Signal_Eligible') is True
                    
                    # Calcular confianza AI
                    conf_data = learner.get_confidence(ticker, r.get('Sector', ''), r.get('RSI', 50))
                    confidence_value = conf_data.get('confidence') if conf_data.get('available') else None
                    ai_confidence = confidence_value / 100.0 if confidence_value is not None else None
                    
                    action = None
                    reason = ""
                    confidence_passes = ai_confidence is not None and ai_confidence >= min_confidence
                    if signal_eligible and signal_state == 'COMPRAR' and confidence_passes and cfg.get('alert_on_buy', True):
                        action = "buy"
                        reason = f"Estado {signal_state}, heurística {r.get('Heuristic_Version')} y confianza AI ({ai_confidence*100:.1f}%). {r.get('Nota', '')}"
                    elif signal_eligible and signal_state in {'REDUCIR', 'SALIR'} and confidence_passes and cfg.get('alert_on_sell', True):
                        action = "sell"
                        reason = f"Estado {signal_state}, heurística {r.get('Heuristic_Version')} y confianza AI ({ai_confidence*100:.1f}%). {r.get('Nota', '')}"
                        
                    if action and not learner.has_recent_alert(ticker, action):
                        # Enviar alerta Telegram
                        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
                        chat_id = resolve_telegram_chat_id(
                            root_dir, token, os.getenv("TELEGRAM_CHAT_ID", "")
                        )
                            
                        if token and chat_id:
                            import requests
                            emoji = "[GREEN] COMPRAR" if action == "buy" else "[RED] VENDER"
                            msg = f"[BOLT] *ALERTA EN VIVO: {ticker}* {emoji}\n\n"
                            msg += f"*Precio:* ${price}\n"
                            msg += f"*Score:* {score} ({viabilidad})\n"
                            msg += f"*Confianza IA:* {ai_confidence*100:.1f}%\n"
                            msg += f"*Razón:* {reason}\n"
                            
                            res = requests.post(
                                f"https://api.telegram.org/bot{token}/sendMessage",
                                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                                timeout=10
                            )
                            if res.status_code == 200:
                                learner.record_live_alert(
                                    ticker=ticker,
                                    price=price,
                                    signal_type=action,
                                    reason=reason,
                                    confidence=ai_confidence,
                                )
                                logger.info(f"Alerta enviada para {ticker}: {action}")
                            else:
                                logger.error(f"Error Telegram: {res.text}")
                except Exception as e:
                    logger.error(f"Error procesando {ticker} en alertas en vivo: {e}")
                    
        except Exception as e:
            logger.error(f"Error en loop de alertas en vivo: {e}")

        # Dormir el intervalo configurado
        _time.sleep(interval * 60)

_background_tasks_started = False


def start_background_tasks():
    """Iniciar tareas de fondo DESPUÉS de que el servidor esté corriendo.
    
    Esto evita que hilos pesados compitan por CPU durante el arranque.
    """
    global _background_tasks_started
    if _background_tasks_started:
        return
    _background_tasks_started = True
    _ensure_visor_loaded()

    # Cargar persistencia de escaneo en hilo separado (521KB JSON)
    def _deferred_load():
        _time.sleep(3)  # Esperar a que el servidor esté listo
        _load_scan_persistence()
        logger.info("Persistencia de escaneo cargada.")
    threading.Thread(target=_deferred_load, name="ScanPersistence", daemon=True).start()
    
    # Hilos de escaneo automático
    threading.Thread(target=run_auto_scan_loop, name="AutoScan-Bolsa", daemon=True).start()
    threading.Thread(target=run_live_alert_loop, name="LiveAlerts-Bolsa", daemon=True).start()
    threading.Thread(target=run_prediction_recovery_loop, name="PredictionRecovery-Bolsa", daemon=True).start()
    logger.info("Tareas de fondo iniciadas (diferidas).")



# ─── Caché de vistas HTML ────────────────────────────────────────────────────
_VIEW_TTL = 30   # segundos
_view_cache: dict = {
    'dashboard':    {'html': None, 'ts': 0.0},
    'transactions': {'html': None, 'ts': 0.0},
    'details':      {'html': None, 'ts': 0.0},
}


def _get_cached_view(key: str):
    entry = _view_cache.get(key)
    if entry and entry['html'] and (_time.time() - entry['ts']) < _VIEW_TTL:
        return entry['html']
    return None


def _set_cached_view(key: str, html: str):
    _view_cache[key] = {'html': html, 'ts': _time.time()}


def _invalidate_views():
    for k in _view_cache:
        _view_cache[k] = {'html': None, 'ts': 0.0}
    db_manager._cache_last_check = 0.0


# ─── Helper: respuesta HTML ──────────────────────────────────────────────────
def _html_response(html: str, cache_seconds: int = 0):
    """Devuelve una respuesta HTML plana (sin compresión manual).
    
    NOTA: La compresión gzip manual fue eliminada porque provocaba
    doble-compresión cuando se accede a través de Cloudflare Tunnel,
    resultando en datos ilegibles (caracteres extraños) en el navegador.
    Cloudflare y/o el proxy inverso se encargan de comprimir automáticamente.
    """
    headers: dict = {'Content-Type': 'text/html; charset=utf-8'}

    if cache_seconds > 0:
        headers['Cache-Control'] = f'public, max-age={cache_seconds}'
    else:
        headers.update({
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        })

    resp = make_response(html)
    resp.headers.update(headers)
    return resp


# ─── Rutas principales ───────────────────────────────────────────────────────
@app.route('/')
def index():
    resp = make_response('', 302)
    resp.headers['Location'] = '/dashboard'
    return resp


@app.route('/dashboard')
def dashboard():
    try:
        year = request.args.get('year')
        available_years = db_manager.get_available_years()

        if year and year.isdigit():
            year_int = int(year)
            cache_key = f'dashboard_{year_int}'
        else:
            year_int = None
            cache_key = 'dashboard_all'

        cached = _get_cached_view(cache_key)
        if cached:
            return _html_response(cached)

        if year_int:
            expenses = db_manager.get_expenses_by_year(year_int)
        else:
            expenses = db_manager.get_all_expenses()

        if not expenses:
            return _html_response(_empty_page('[WARN] Sin gastos', 'La base de datos está vacía.'))

        categories = db_manager.get_categories()
        data = DashboardGenerator.generate_html(expenses, categories, selected_year=year_int, available_years=available_years)
        data['current_time'] = datetime.now().strftime('%d %b %H:%M')
        html = render_template('dashboard.html', **data)
        _set_cached_view(cache_key, html)
        return _html_response(html)

    except Exception as e:
        logger.error(f"Error generando dashboard: {e}", exc_info=True)
        return _html_response(_error_page(sanitize_public_error(e))), 500


@app.route('/transactions')
def transactions_view():
    try:
        year = request.args.get('year')
        available_years = db_manager.get_available_years()

        if year and year.isdigit():
            year = int(year)
            cache_key = f'transactions_{year}'
        else:
            year = None
            cache_key = 'transactions_all'

        cached = _get_cached_view(cache_key)
        if cached:
            return _html_response(cached)

        if year:
            expenses = db_manager.get_expenses_by_year(year)
        else:
            # Evita construir un documento de varios MB en la vista general.
            # El historial completo sigue accesible por las pestañas de año.
            expenses = db_manager.get_expenses(limit=150)

        data = TransactionsViewGenerator.generate_html(expenses, selected_year=year, available_years=available_years)
        data['transactions_hint'] = (
            'Mostrando los 150 movimientos más recientes. Elige un año para consultar su historial completo.'
            if year is None and len(expenses) >= 150 else ''
        )
        html = render_template('transactions.html', **data)
        _set_cached_view(cache_key, html)
        return _html_response(html)

    except Exception as e:
        logger.error(f"Error generando transacciones: {e}", exc_info=True)
        return _html_response(_error_page(sanitize_public_error(e))), 500


@app.route('/details')
def details_view():
    try:
        cached = _get_cached_view('details')
        if cached:
            return _html_response(cached)

        expenses = db_manager.get_all_expenses()
        data = DetailsViewGenerator.generate_html(expenses)
        html = render_template('details.html', **data)
        _set_cached_view('details', html)
        return _html_response(html)

    except Exception as e:
        logger.error(f"Error generando detalles: {e}", exc_info=True)
        return _html_response(_error_page(sanitize_public_error(e))), 500


# ─── API: gastos ─────────────────────────────────────────────────────────────
@app.route('/api/add-expense', methods=['POST'])
def add_expense():
    data = request.get_json(force=True) or {}
    if not data:
        return jsonify({'success': False, 'message': 'Payload vacío'}), 400
    success, message = db_manager.add_expense(data)
    _invalidate_views()
    status_code = 201 if success else 400
    return jsonify({'success': success, 'message': message}), status_code


@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    try:
        expenses = db_manager.get_all_expenses()
        return jsonify({'success': True, 'expenses': expenses, 'count': len(expenses)})
    except Exception as e:
        return jsonify({'success': False, 'message': sanitize_public_error(e)}), 500


@app.route('/api/update-expense', methods=['POST'])
def update_expense():
    data = request.get_json(force=True) or {}
    expense_id = data.get('id')
    if not expense_id:
        return jsonify({'success': False, 'message': 'ID faltante'}), 400
    success, message = db_manager.update_expense(expense_id, data)
    if success:
        _invalidate_views()
    return jsonify({'success': success, 'message': message})


@app.route('/api/delete-expense', methods=['POST'])
def delete_expense():
    data = request.get_json(force=True) or {}
    expense_id = data.get('id')
    if not expense_id:
        return jsonify({'success': False, 'message': 'ID faltante'}), 400
    success, message = db_manager.delete_expense(expense_id)
    if success:
        _invalidate_views()
    return jsonify({'success': success, 'message': message})


@app.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        cats = db_manager.get_categories()
        return jsonify({'success': True, 'categories': cats})
    except Exception as e:
        return jsonify({'success': False, 'message': sanitize_public_error(e)}), 500


@app.route('/api/get-settings', methods=['GET'])
def get_settings():
    try:
        return jsonify({'success': True, 'settings': db_manager.get_all_settings()})
    except Exception as e:
        return jsonify({'success': False, 'message': sanitize_public_error(e)}), 500


@app.route('/api/set-setting', methods=['POST'])
def set_setting():
    data = request.get_json(force=True) or {}
    key = data.get('key')
    value = data.get('value')
    if not key:
        return jsonify({'success': False, 'message': 'Key faltante'}), 400
    success, message = db_manager.set_setting(key, str(value))
    return jsonify({'success': success, 'message': message})


@app.route('/api/export-excel')
def export_excel():
    try:
        import tempfile
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Reporte_Gastos_{timestamp}.xlsx"
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        success, result_path = ExcelExporter.export_from_database(db_manager, temp_path)
        if success:
            return send_file(
                result_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
        return f"Error generando Excel: {result_path}", 500
    except Exception as e:
        logger.error(f"Error en /api/export-excel: {e}", exc_info=True)
        return f"Error: {e}", 500


@app.route('/api/send-to-telegram', methods=['POST'])
def send_to_telegram():
    import base64, tempfile, asyncio
    data = request.get_json(force=True) or {}
    if 'image' not in data:
        return jsonify({"success": False, "message": "No hay imagen"}), 400

    try:
        img_bytes = base64.b64decode(data['image'].split(',')[1])
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        bot_instance = app.config.get('BOT_INSTANCE')
        if not bot_instance:
            return jsonify({"success": False, "message": "Bot no disponible"}), 503

        caption = data.get('caption', '[CHART_BAR] Exportación de Dashboard')
        future = asyncio.run_coroutine_threadsafe(
            bot_instance.send_photo(tmp_path, caption=caption),
            bot_instance._loop,
        )
        success, message = future.result(timeout=20)
    except Exception as e:
        return jsonify({"success": False, "message": sanitize_public_error(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return jsonify({"success": success, "message": message})


# ─── Rutas de Bolsa (refactor v2.7.1: robusto + diagnóstico) ────────────────
@app.route('/bolsa', strict_slashes=False)
@app.route('/bolsa/', strict_slashes=False)
def bolsa_view():
    """Sirve el visor /bolsa con manejo de errores y sin caché.

    RECTIFICA v2.7.1: antes era un send_from_directory sin try/except;
    si index.html faltaba o había un error, Werkzeug devolvía un 404
    genérico y en LAN parecía que 'no abre'. Ahora loguea y devuelve
    una página de error legible con estado 500/404 explícito.
    """
    try:
        visor_dir = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT')
        index_path = os.path.join(visor_dir, 'index.html')
        if not os.path.isfile(index_path):
            logger.error(f"/bolsa: index.html no encontrado en {visor_dir}")
            return _html_response(_error_page("/bolsa: index.html no encontrado")), 404
        resp = send_from_directory(visor_dir, 'index.html')
        # Sin caché: el visor cambia seguido (ml, theme) y el ?v= ya versiona assets
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    except Exception as e:
        logger.error(f"Error sirviendo /bolsa: {e}", exc_info=True)
        return _html_response(_error_page(sanitize_public_error(e))), 500


@app.route('/visor/<path:path>')
def serve_visor_static(path):
    try:
        visor_dir = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT')
        return send_from_directory(visor_dir, path)
    except Exception as e:
        logger.error(f"Error sirviendo /visor/{path}: {e}")
        return jsonify({'status': 'error', 'message': f'Asset no encontrado: {path}'}), 404


@app.route('/api/bolsa/health', methods=['GET'])
def bolsa_health():
    """Diagnóstico rápido para 'no abre en LAN': verifica archivos y motor."""
    try:
        visor_dir = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT')
        checks = {
            'index_html': os.path.isfile(os.path.join(visor_dir, 'index.html')),
            'app_js': os.path.isfile(os.path.join(visor_dir, 'app.js')),
            'style_css': os.path.isfile(os.path.join(visor_dir, 'style.css')),
            'flux_theme': os.path.isfile(os.path.join(root_dir, 'src', 'static', 'flux_theme.css')),
            'liquidGL': os.path.isfile(os.path.join(root_dir, 'src', 'static', 'liquidGL.js')),
            'particle_fluid': os.path.isfile(os.path.join(root_dir, 'src', 'static', 'particle_fluid.js')),
            'visor_import_error': visor_import_error,
            'scan_engine': bool(fetch_stock_data),
            'recent_errors': application_errors.summary(),
        }
        ok = all([checks['index_html'], checks['app_js'], checks['style_css']])
        
        # Ampliación para Fase 1
        db_path = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT', 'learner.db')
        return jsonify({
            'status': 'ok' if ok else 'error', 
            'version': '3.0.1',
            'build': 'error-hardening',
            'db_exists': os.path.exists(db_path),
            'provider': 'yahoo_chart_v8',
            'checks': checks
        }), (200 if ok else 503)
    except Exception as e:
        return jsonify({'status': 'error', 'message': sanitize_public_error(e)}), 500


@app.route('/api/bolsa/client-errors', methods=['GET', 'POST'])
def bolsa_client_errors():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        item = application_errors.record({
            'message': data.get('message'), 'component': data.get('component', 'bolsa-ui'),
            'source': data.get('source'), 'line': data.get('line'),
            'correlation_id': getattr(g, 'correlation_id', ''),
        })
        logger.warning("Error cliente clasificado [%s]: %s", item['category'], item['message'])
        return jsonify({'status': 'recorded', 'error': item}), 202
    return jsonify({'status': 'ok', 'errors': application_errors.summary(),
                    'categories': ERROR_CATEGORIES})

@app.route('/api/bolsa/readiness', methods=['GET'])
def bolsa_readiness():
    # Solo 200 cuando API, base y UI mínima puedan servir tráfico
    try:
        db_path = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT', 'learner.db')
        if not os.path.exists(db_path):
            return jsonify({'status': 'error', 'message': 'Base de datos no encontrada'}), 503
        
        visor_dir = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT')
        if not os.path.isfile(os.path.join(visor_dir, 'index.html')):
            return jsonify({'status': 'error', 'message': 'UI mínima no encontrada'}), 503
            
        if not fetch_stock_data:
            return jsonify({'status': 'error', 'message': 'Motor de escaneo no disponible'}), 503
            
        return jsonify({'status': 'ready'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': sanitize_public_error(e)}), 500


@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    if SCAN_STATE['is_scanning']:
        return jsonify({'status': 'error', 'message': 'Scan ya en progreso'}), 409

    data = request.get_json(force=True) or {}
    kwargs = {
        'use_cache':   data.get('use_cache', True),
        'max_workers': int(data.get('max_workers', 15)),
        'source':      data.get('source', 'all'),
    }
    threading.Thread(target=_run_scan_worker, kwargs=kwargs, daemon=True).start()
    return jsonify({'status': 'ok', 'message': 'Escaneo iniciado'})


@app.route('/api/scan/stop', methods=['POST'])
def stop_scan():
    if SCAN_STATE['is_scanning']:
        SCAN_STATE['stop_event'].set()
    return jsonify({'status': 'ok', 'message': 'Señal de parada enviada'})


@app.route('/api/scan/status', methods=['GET'])
def scan_status():
    if not SCAN_STATE['results']:
        _load_scan_persistence()
    er = SCAN_STATE.get('exchange_rate', 20.5)
    if not SCAN_STATE['results'] and SCAN_STATE.get('exchange_rate') is None:
        pass  # mantener fallback
    elif SCAN_STATE['results']:
        for r in SCAN_STATE['results']:
            if 'Price_MXN' in r and r.get('Price'):
                er = round(r['Price_MXN'] / r['Price'], 4)
                break
    now_utc = datetime.now(timezone.utc)
    market_open = _is_market_hours(now_utc)
    return jsonify({
        'is_scanning':   SCAN_STATE['is_scanning'],
        'progress':      SCAN_STATE['progress'],
        'message':       SCAN_STATE['message'],
        'results_count': len(SCAN_STATE['results']),
        'exchange_rate': er,
        'automation': {
            **AUTO_SCAN_STATE,
            'market_open': market_open,
            'schedule': 'NYSE 09:30-16:00 America/New_York; respeta festivos y medias sesiones',
            'next_market_open_utc': None if market_open else next_nyse_open(now_utc).isoformat().replace('+00:00', 'Z'),
        },
    })


@app.route('/api/scan/results', methods=['GET'])
def get_results():
    if not SCAN_STATE['results']:
        _load_scan_persistence()
    if SCAN_STATE['is_scanning']:
        return jsonify({'status': 'error', 'message': 'Escaneo en progreso'}), 409
    er = SCAN_STATE.get('exchange_rate', 20.5)
    for r in SCAN_STATE['results']:
        if 'Price_MXN' in r and r.get('Price', 0) > 0:
            er = round(r['Price_MXN'] / r['Price'], 4)
            break
    results = SCAN_STATE['results']
    kill_status = operations_kill_switch.status()
    if kill_status['active']:
        results = [{**row, 'Signal_State': 'SIN SEÑAL', 'Signal_Eligible': False,
                    'Kill_Switch': {'active': True, 'reason': kill_status['reason']}}
                   for row in results]
    operations_metrics.signal_count = len(results)
    operations_metrics.stale_data_count = sum(bool((row.get('Quote') or {}).get('is_stale')) for row in results)
    return jsonify({
        'status':          'ok',
        'data_contract_version': '3.0',
        'results':        results,
        'market_context': SCAN_STATE['market_context'],
        'exchange_rate':  er,
        'generated_at_utc': SCAN_STATE.get('generated_at_utc'),
    })


@app.route('/api/bolsa/operations', methods=['GET'])
def bolsa_operations():
    return jsonify({'status': 'ok', 'metrics': operations_metrics.snapshot(),
                    'kill_switch': operations_kill_switch.status()})


@app.route('/api/bolsa/release-status', methods=['GET'])
def bolsa_release_status():
    return jsonify({'status': 'ok', 'release': current_project_gate()})


@app.route('/api/bolsa/maturity', methods=['GET'])
def bolsa_maturity_status():
    if not paper_ledger or not phase9_approval_fn:
        return jsonify({'status': 'error', 'message': 'Estado de madurez no disponible'}), 503
    metrics = paper_ledger.metrics()
    paper_gate = phase9_approval_fn(
        metrics, availability=None, live_backtest_deviation=None,
        net_expected_value=None, drawdown_within_limit=None,
    )
    maturity = build_maturity_status(
        paper_metrics=metrics,
        paper_gate=paper_gate,
        release_gate=current_project_gate(),
        scan_results=SCAN_STATE.get('results', []),
    )
    return jsonify({'status': 'ok', 'maturity': maturity})


@app.route('/api/bolsa/operations/kill-switch', methods=['POST'])
def set_operations_kill_switch():
    data = request.get_json(silent=True) or {}
    actor = str(data.get('actor') or '').strip()
    reason = str(data.get('reason') or '').strip()
    if not actor or not reason or not isinstance(data.get('active'), bool):
        return jsonify({'status': 'error', 'message': 'active, reason y actor son obligatorios'}), 400
    state = operations_kill_switch.set(data['active'], reason, actor)
    return jsonify({'status': 'ok', 'kill_switch': state})


@app.route('/api/bolsa/paper/status', methods=['GET'])
def paper_trading_status():
    if not paper_ledger or not phase9_approval_fn:
        return jsonify({'status': 'error', 'message': 'Paper trading no disponible'}), 503
    metrics = paper_ledger.metrics()
    gate = phase9_approval_fn(
        metrics, availability=None, live_backtest_deviation=None,
        net_expected_value=None, drawdown_within_limit=None,
    )
    return jsonify({
        'status': 'ok', 'mode': 'paper_trading', 'protocol': paper_protocol,
        'metrics': metrics, 'approval': gate,
        'notice': 'Sin dinero real; extender hasta completar la muestra prospectiva.',
    })


@app.route('/api/bolsa/transparency', methods=['GET'])
def bolsa_transparency():
    if not all((signal_explanation_fn, adaptive_ai_status_fn, paper_ledger, phase9_approval_fn)):
        return jsonify({'status': 'error', 'message': 'Transparencia no disponible'}), 503
    paper_metrics = paper_ledger.metrics()
    paper_gate = phase9_approval_fn(
        paper_metrics, availability=None, live_backtest_deviation=None,
        net_expected_value=None, drawdown_within_limit=None,
    )
    ml = get_ml_predictor().get_status() if get_ml_predictor else {}
    learner = get_learner().get_stats() if get_learner else {}
    return jsonify({
        'status': 'ok',
        'adaptive_ai': adaptive_ai_status_fn(ml_status=ml, learner_stats=learner, paper_status=paper_gate),
        'paper_trading': {'metrics': paper_metrics, 'approval': paper_gate},
        'signals': [signal_explanation_fn(row, SCAN_STATE.get('generated_at_utc')) for row in SCAN_STATE['results']],
    })


# ── IA Adaptativa (Learner) ──────────────────────────────────────────────────
@app.route('/api/learner/stats', methods=['GET'])
def learner_stats():
    if not get_learner:
        return jsonify({'status': 'error', 'message': 'Learner no disponible'}), 503
    return jsonify({'status': 'ok', 'stats': get_learner().get_stats()})


@app.route('/api/learner/history', methods=['GET'])
def learner_history():
    if not get_learner:
        return jsonify({'status': 'error', 'message': 'Learner no disponible'}), 503
    limit = request.args.get('limit', 50, type=int)
    history = get_learner().get_history(limit)
    filters = {name: request.args.get(name) for name in
               ('date_from', 'date_to', 'ticker', 'model', 'signal', 'horizon', 'result')}
    if filter_history_fn:
        history = filter_history_fn(history, **filters)
    return jsonify({'status': 'ok', 'history': history, 'filters': filters})


@app.route('/api/learner/feedback', methods=['POST'])
def learner_feedback():
    if not get_learner:
        return jsonify({'status': 'error', 'message': 'Learner no disponible'}), 503
    data = request.get_json(force=True) or {}
    required = ('prediction_id', 'feedback', 'reason', 'user_id', 'user_role')
    missing = [field for field in required if not data.get(field)]
    if missing:
        return jsonify({'status': 'error', 'message': f"Campos requeridos: {', '.join(missing)}"}), 400
    try:
        feedback_id = get_learner().submit_user_feedback(
            data['prediction_id'], data['feedback'], data['reason'],
            data['user_id'], data['user_role'], data.get('note', '')
        )
    except (ValueError, KeyError) as exc:
        return jsonify({'status': 'error', 'message': sanitize_public_error(exc)}), 400
    return jsonify({'status': 'ok', 'message': 'Feedback registrado', 'feedback_id': feedback_id})


# ── Machine Learning (Predictor) ─────────────────────────────────────────────
@app.route('/api/ml/status', methods=['GET'])
def ml_status():
    if not get_ml_predictor:
        return jsonify({'status': 'error', 'message': 'ML Predictor no disponible'}), 503
    return jsonify({'status': 'ok', 'ml': get_ml_predictor().get_status()})


@app.route('/api/ml/retrain', methods=['POST'])
def ml_retrain():
    if not get_ml_predictor:
        return jsonify({'status': 'error', 'message': 'ML Predictor no disponible'}), 503
    try:
        metrics = get_ml_predictor().train_model()
        return jsonify({'status': 'ok', 'metrics': metrics})
    except Exception as e:
        logger.error(f"Error reentrenando modelo ML: {e}")
        return jsonify({'status': 'error', 'message': sanitize_public_error(e)}), 500


@app.route('/api/cache/stats', methods=['GET'])
def cache_stats():
    if not get_cache_stats:
        return jsonify({'status': 'error', 'message': 'Motor de escaneo no disponible'}), 503
    return jsonify({
        'data_cache': get_cache_stats(),
        'ticker_cache': get_ticker_cache_stats() if 'get_ticker_cache_stats' in globals() else {}
    })


@app.route('/api/cache/clear', methods=['POST'])
def clear_all_cache():
    if clear_cache:
        clear_cache()
    if 'clear_ticker_cache' in globals() and clear_ticker_cache:
        clear_ticker_cache()
    return jsonify({'status': 'ok'})


@app.route('/api/risk/calculate', methods=['POST'])
def calc_risk():
    data = request.get_json(force=True) or {}
    try:
        capital        = float(data.get('capital', 10000))
        price          = float(data.get('price', 0))
        atr            = float(data.get('atr', 0))
        risk_pct       = float(data.get('risk_pct', 2)) / 100.0
        atr_multiplier = float(data.get('atr_multiplier', 2))
        return jsonify(calculate_position_size(capital, price, atr, risk_pct, atr_multiplier))
    except Exception as e:
        return jsonify({'error': sanitize_public_error(e)}), 400


@app.route('/api/portfolio/config', methods=['GET', 'POST'])
def portfolio_config():
    if not config_mgr:
        return jsonify({'status': 'error', 'message': 'ConfigManager no disponible'}), 503
    
    if request.method == 'POST':
        data = request.get_json(force=True) or {}
        
        # Acción de eliminar
        if data.get('action') == 'remove':
            ticker = data.get('ticker')
            if ticker:
                config_mgr.remove_from_portfolio(ticker)
                return jsonify({'status': 'ok'})

        # Soporte para lista (retrocompatibilidad) o dict
        new_portfolio = data.get('portfolio', {})
        if isinstance(new_portfolio, list):
            # Convertir lista de tickers a dict
            new_portfolio = {t.upper(): {'qty': 0, 'avg_price': 0} for t in new_portfolio}
        
        config_mgr.config['portfolio'] = new_portfolio
        config_mgr.save_config()
        return jsonify({'status': 'ok'})
        
    return jsonify({'portfolio': config_mgr.get_portfolio()})


@app.route('/api/portfolio/update', methods=['POST'])
def update_portfolio_item():
    if not config_mgr: return jsonify({'status': 'error'}), 503
    data = request.get_json(force=True) or {}
    ticker = data.get('ticker')
    qty = data.get('qty', 0)
    price = data.get('price', 0)
    if not ticker: return jsonify({'status': 'error', 'message': 'Ticker faltante'}), 400
    
    config_mgr.update_portfolio_item(ticker, qty, price)
    return jsonify({'status': 'ok'})


@app.route('/api/portfolio/analyze', methods=['GET', 'POST'])
def analyze_portfolio_api():
    if not config_mgr: return jsonify({'status': 'error'}), 503
    
    portfolio = config_mgr.get_portfolio()
    try:
        from portfolio_analyzer import analyze_portfolio
        quote_overrides = {}
        for result in SCAN_STATE.get('results', []):
            quote = result.get('Quote')
            if isinstance(quote, dict) and quote.get('symbol'):
                quote_overrides[quote['symbol']] = quote
        results = analyze_portfolio(portfolio, quote_overrides=quote_overrides)
        return jsonify({'status': 'ok', 'results': results})
    except Exception as e:
        logger.error(f"Error analizando portafolio: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': sanitize_public_error(e)}), 500

@app.route('/api/dashboard-updates')
def dashboard_updates():
    try:
        data = db_manager.get_dashboard_summary()
        
        now = datetime.now()
        _, days_in_month = calendar.monthrange(now.year, now.month)
        
        month_total = float(data.get('month_total', 0))
        effective_days = max(now.day, 7)
        daily_avg = month_total / effective_days if effective_days > 0 else 0
        monthly_projection = daily_avg * days_in_month
        
        return jsonify({'success': True, 'data': {
            'total_amount': round(float(data.get('total', 0)), 2),
            'daily_avg': round(daily_avg, 2),
            'monthly_projection': round(monthly_projection, 2),
            'total_loan': round(float(data.get('loan', 0)), 2),
            'total_debt': round(float(data.get('debt', 0)), 2),
        }})
    except Exception as e:
        logger.error(f"Error en dashboard-updates: {e}")
        return jsonify({'success': False, 'message': sanitize_public_error(e)}), 500


# ─── Cache de estáticos ──────────────────────────────────────────────────────
from flask import send_from_directory

@app.route('/static/<path:filename>')
def serve_static(filename):
    res = make_response(send_from_directory(
        os.path.join(root_dir, 'src', 'static'), 
        filename, 
        max_age=0
    ))
    res.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    res.headers['Pragma'] = 'no-cache'
    res.headers['Expires'] = '0'
    return res

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _empty_page(title: str, body: str) -> str:
    return (
        f"<!DOCTYPE html><html><head><title>{title}</title>"
        "<style>body{font-family:Arial,sans-serif;display:flex;justify-content:center;"
        "align-items:center;height:100vh;margin:0;background:#050a14;color:white;}</style>"
        f"</head><body><div><h1>{title}</h1><p>{body}</p></div></body></html>"
    )


def _error_page(error: str) -> str:
    return (
        "<!DOCTYPE html><html><head><title>Error</title>"
        "<style>body{font-family:Arial,sans-serif;padding:20px;background:#050a14;color:white;}</style>"
        f"</head><body><h1>[X] Error</h1><pre>{error}</pre></body></html>"
    )


def run_server(host: str = '0.0.0.0', port: int = 5050, debug: bool = False,
               bot_instance=None, start_jobs: bool | None = None):
    if bot_instance:
        app.config['BOT_INSTANCE'] = bot_instance
    logger.warning(f"[TUNNEL] Servidor iniciado en http://{host}:{port}")
    
    if start_jobs is None:
        start_jobs = os.environ.get('ENABLE_BOLSA_BACKGROUND_TASKS', '1').strip().lower() not in {'0', 'false', 'no'}
    if start_jobs:
        start_background_tasks()
    else:
        logger.info("Tareas automáticas de Bolsa desactivadas (inicio rápido).")
    
    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)


if __name__ == '__main__':
    run_server(debug=False)
