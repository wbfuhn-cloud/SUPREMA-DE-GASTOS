from flask import Flask, jsonify, request, make_response, send_file, send_from_directory, render_template
from flask_cors import CORS  # type: ignore
import sys
import os
import logging
from datetime import datetime
import threading
import time as _time
import json
import calendar

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
try:
    from stock_scanner import fetch_stock_data, get_cache_stats, clear_cache, get_ticker_cache_stats, clear_ticker_cache, process_single_ticker  # type: ignore
    from risk_calculator import calculate_position_size  # type: ignore
    from config_manager import ConfigManager  # type: ignore
    from portfolio_analyzer import analyze_portfolio  # type: ignore
    from recommendation_learner import get_learner  # type: ignore
    from ml_predictor import get_ml_predictor  # type: ignore
except ImportError as e:
    visor_import_error = str(e)
    logger.error(f"Error importando módulos de VISOR: {e}")
    fetch_stock_data = None
    process_single_ticker = None # type: ignore
    calculate_position_size = lambda *args, **kwargs: {}  # Fallback callable
    ConfigManager = None  # type: ignore
    analyze_portfolio = None  # type: ignore
    get_learner = None # type: ignore
    get_ml_predictor = None # type: ignore

config_mgr = ConfigManager() if ConfigManager is not None else None

# ─── Flask ───────────────────────────────────────────────────────────────────
app = Flask(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
CORS(app)

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
    'stop_event':     threading.Event(),
}

SCAN_CACHE_FILE = os.path.join(root_dir, 'database', 'last_scan_results.json')

def _load_scan_persistence():
    """Carga el último escaneo guardado desde disco."""
    if os.path.exists(SCAN_CACHE_FILE):
        try:
            with open(SCAN_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                SCAN_STATE['results'] = data.get('results', [])
                SCAN_STATE['market_context'] = data.get('market_context')
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
                'timestamp': datetime.now().isoformat()
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
    """Retorna True si el mercado NYSE está (aprox.) abierto."""
    if now.weekday() >= 5:          # sábado / domingo
        return False
    h, m = now.hour, now.minute
    return (h == 8 and m >= 30) or (9 <= h < 13) or (h == 13 and m <= 30)


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
        except Exception:
            pass

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
            _save_scan_persistence()
            
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
                chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
                if not chat_id:
                    try:
                        with open(os.path.join(root_dir, "data", "chat_id.txt"), "r") as f:
                            chat_id = f.read().strip()
                    except: pass
                
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
    """Ejecuta un escaneo automático cada hora durante horario de mercado."""
    logger.info("[AI] Hilo de auto-escaneo iniciado.")
    _time.sleep(30)   # respirar al inicio

    while True:
        try:
            if _is_market_hours(datetime.now()) and not SCAN_STATE['is_scanning'] and fetch_stock_data:
                logger.info("[SCAN] Ejecutando escaneo programado...")
                threading.Thread(target=_run_scan_worker, daemon=True).start()
        except Exception as e:
            logger.error(f"Error en loop de auto-escaneo: {e}")

        _time.sleep(3600)   # revisar cada hora





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
                    score = r.get('Score', 0)
                    price = r.get('Price', 0.0)
                    viabilidad = r.get('Viabilidad', '')
                    
                    # Calcular confianza AI
                    conf_data = learner.get_confidence(ticker, r.get('Sector', ''), r.get('RSI', 50))
                    ai_confidence = conf_data['confidence'] / 100.0
                    
                    action = None
                    reason = ""
                    if score >= 75 and ai_confidence >= min_confidence and cfg.get('alert_on_buy', True):
                        action = "buy"
                        reason = f"Score alto ({score}) y confianza AI ({ai_confidence*100:.1f}%). {r.get('Nota', '')}"
                    elif score <= 25 and ai_confidence >= min_confidence and cfg.get('alert_on_sell', True):
                        action = "sell"
                        reason = f"Score bajo ({score}) y confianza AI ({ai_confidence*100:.1f}%). {r.get('Nota', '')}"
                        
                    if action and not learner.has_recent_alert(ticker, action):
                        # Enviar alerta Telegram
                        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
                        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
                        if not chat_id:
                            try:
                                with open(os.path.join(root_dir, "data", "chat_id.txt"), "r") as f:
                                    chat_id = f.read().strip()
                            except: pass
                            
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
                                learner.record_live_alert(ticker, action, price, ai_confidence, reason)
                                logger.info(f"Alerta enviada para {ticker}: {action}")
                            else:
                                logger.error(f"Error Telegram: {res.text}")
                except Exception as e:
                    logger.error(f"Error procesando {ticker} en alertas en vivo: {e}")
                    
        except Exception as e:
            logger.error(f"Error en loop de alertas en vivo: {e}")

        # Dormir el intervalo configurado
        _time.sleep(interval * 60)

def start_background_tasks():
    """Iniciar tareas de fondo DESPUÉS de que el servidor esté corriendo.
    
    Esto evita que hilos pesados compitan por CPU durante el arranque.
    """
    # Cargar persistencia de escaneo en hilo separado (521KB JSON)
    def _deferred_load():
        _time.sleep(3)  # Esperar a que el servidor esté listo
        _load_scan_persistence()
        logger.info("Persistencia de escaneo cargada.")
    threading.Thread(target=_deferred_load, name="ScanPersistence", daemon=True).start()
    
    # Hilos de escaneo automático
    threading.Thread(target=run_auto_scan_loop, name="AutoScan-Bolsa", daemon=True).start()
    threading.Thread(target=run_live_alert_loop, name="LiveAlerts-Bolsa", daemon=True).start()
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
        return _html_response(_error_page(str(e))), 500


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
            expenses = db_manager.get_all_expenses()

        data = TransactionsViewGenerator.generate_html(expenses, selected_year=year, available_years=available_years)
        html = render_template('transactions.html', **data)
        _set_cached_view(cache_key, html)
        return _html_response(html)

    except Exception as e:
        logger.error(f"Error generando transacciones: {e}", exc_info=True)
        return _html_response(_error_page(str(e))), 500


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
        return _html_response(_error_page(str(e))), 500


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
        return jsonify({'success': False, 'message': str(e)}), 500


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
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/get-settings', methods=['GET'])
def get_settings():
    try:
        return jsonify({'success': True, 'settings': db_manager.get_all_settings()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return jsonify({"success": success, "message": message})


# ─── Rutas de Bolsa ──────────────────────────────────────────────────────────
@app.route('/bolsa')
def bolsa_view():
    visor_dir = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT')
    return send_from_directory(visor_dir, 'index.html')


@app.route('/visor/<path:path>')
def serve_visor_static(path):
    visor_dir = os.path.join(root_dir, 'tools', 'NOTIFICADOR_BOT')
    return send_from_directory(visor_dir, path)


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
    return jsonify({
        'is_scanning':   SCAN_STATE['is_scanning'],
        'progress':      SCAN_STATE['progress'],
        'message':       SCAN_STATE['message'],
        'results_count': len(SCAN_STATE['results']),
        'exchange_rate': er,
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
    return jsonify({
        'results':        SCAN_STATE['results'],
        'market_context': SCAN_STATE['market_context'],
        'exchange_rate':  er,
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
    return jsonify({'status': 'ok', 'history': get_learner().get_history(limit)})


@app.route('/api/learner/feedback', methods=['POST'])
def learner_feedback():
    if not get_learner:
        return jsonify({'status': 'error', 'message': 'Learner no disponible'}), 503
    data = request.get_json(force=True) or {}
    ticker = data.get('ticker')
    feedback = data.get('feedback', 'bad')
    if not ticker:
        return jsonify({'status': 'error', 'message': 'Ticker requerido'}), 400
    
    get_learner().submit_user_feedback(ticker, feedback)
    return jsonify({'status': 'ok', 'message': 'Feedback registrado'})


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
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        return jsonify({'error': str(e)}), 400


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


@app.route('/api/portfolio/analyze', methods=['POST'])
def analyze_portfolio_api():
    if not config_mgr: return jsonify({'status': 'error'}), 503
    
    portfolio = config_mgr.get_portfolio()
    try:
        from portfolio_analyzer import analyze_portfolio
        results = analyze_portfolio(portfolio)
        return jsonify({'status': 'ok', 'results': results})
    except Exception as e:
        logger.error(f"Error analizando portafolio: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        return jsonify({'success': False, 'message': str(e)}), 500


# ─── Cache de estáticos ──────────────────────────────────────────────────────
from flask import send_from_directory

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(
        os.path.join(root_dir, 'src', 'static'), 
        filename, 
        max_age=86400  # Cache 24 horas
    )

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


def run_server(host: str = '0.0.0.0', port: int = 5050, debug: bool = False, bot_instance=None):
    if bot_instance:
        app.config['BOT_INSTANCE'] = bot_instance
    logger.warning(f"[TUNNEL] Servidor iniciado en http://{host}:{port}")
    
    # Iniciar procesos de fondo diferidos (Bolsa y Persistencia)
    start_background_tasks()
    
    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)


if __name__ == '__main__':
    run_server(debug=True)
