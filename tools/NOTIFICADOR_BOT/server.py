import os
import sys
import threading
import json
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import time

# Importar lógica de negocio de VISOR
try:
    from stock_scanner import fetch_stock_data, get_cache_stats, clear_cache, get_ticker_cache_stats, clear_ticker_cache
    from risk_calculator import calculate_position_size
    from config_manager import ConfigManager
    from portfolio_analyzer import analyze_portfolio
except ImportError as e:
    print(f"Error importando módulos de VISOR: {e}")
    sys.exit(1)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

config_mgr = ConfigManager()

# Variables globales para el estado del escaneo
SCAN_STATE = {
    'is_scanning': False,
    'progress': 0.0,
    'message': 'Listo para iniciar',
    'results': [],
    'market_context': None,
    'stop_event': threading.Event()
}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

def update_progress_callback(message, value):
    SCAN_STATE['message'] = message
    SCAN_STATE['progress'] = value

def scan_worker(use_cache, max_workers, source):
    try:
        data = fetch_stock_data(
            progress_callback=update_progress_callback,
            stop_event=SCAN_STATE['stop_event'],
            use_cache=use_cache,
            max_workers=max_workers,
            source=source
        )
        
        if not SCAN_STATE['stop_event'].is_set():
            if isinstance(data, dict):
                SCAN_STATE['results'] = data.get('results', [])
                SCAN_STATE['market_context'] = data.get('market_context', None)
            else:
                SCAN_STATE['results'] = []
                SCAN_STATE['market_context'] = None
            SCAN_STATE['message'] = 'Escaneo Finalizado'
            SCAN_STATE['progress'] = 1.0
        else:
            SCAN_STATE['message'] = 'Escaneo Detenido'
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        SCAN_STATE['message'] = f'Error: {str(e)}'
    finally:
        SCAN_STATE['is_scanning'] = False

@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    if SCAN_STATE['is_scanning']:
        return jsonify({'status': 'error', 'message': 'Scan ya en progreso'}), 400
    
    data = request.json or {}
    source = data.get('source', 'all')
    use_cache = data.get('use_cache', True)
    max_workers = int(data.get('max_workers', 15))
    
    SCAN_STATE['is_scanning'] = True
    SCAN_STATE['progress'] = 0.0
    SCAN_STATE['message'] = 'Iniciando escaneo...'
    SCAN_STATE['results'] = []
    SCAN_STATE['market_context'] = None
    SCAN_STATE['stop_event'].clear()
    
    thread = threading.Thread(target=scan_worker, args=(use_cache, max_workers, source))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'ok', 'message': 'Escaneo iniciado'})

@app.route('/api/scan/stop', methods=['POST'])
def stop_scan():
    if SCAN_STATE['is_scanning']:
        SCAN_STATE['stop_event'].set()
        return jsonify({'status': 'ok', 'message': 'Deteniendo escaneo...'})
    return jsonify({'status': 'ok', 'message': 'No hay escaneo en progreso'})

@app.route('/api/scan/status', methods=['GET'])
def scan_status():
    return jsonify({
        'is_scanning': SCAN_STATE['is_scanning'],
        'progress': SCAN_STATE['progress'],
        'message': SCAN_STATE['message'],
        'results_count': len(SCAN_STATE['results'])
    })

@app.route('/api/scan/results', methods=['GET'])
def get_results():
    if SCAN_STATE['is_scanning']:
        return jsonify({'status': 'error', 'message': 'Escaneo en progreso, espere a que termine'}), 400
    
    return jsonify({
        'results': SCAN_STATE['results'],
        'market_context': SCAN_STATE['market_context']
    })

@app.route('/api/risk/calculate', methods=['POST'])
def calc_risk():
    data = request.json
    try:
        capital = float(data.get('capital', 10000))
        price = float(data.get('price', 0))
        atr = float(data.get('atr', 0))
        risk_pct = float(data.get('risk_pct', 2)) / 100.0
        atr_multiplier = float(data.get('atr_multiplier', 2))
        
        result = calculate_position_size(capital, price, atr, risk_pct, atr_multiplier)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/cache/stats', methods=['GET'])
def cache_stats():
    stats = get_cache_stats()
    t_stats = get_ticker_cache_stats()
    return jsonify({
        'data_cache': stats,
        'ticker_cache': t_stats
    })

@app.route('/api/cache/clear', methods=['POST'])
def clear_caches():
    data = request.json or {}
    target = data.get('target', 'all') # 'data', 'tickers', 'all'
    
    response = {}
    if target in ['data', 'all']:
        deleted = clear_cache()
        response['data_cache_deleted'] = deleted
    
    if target in ['tickers', 'all']:
        success = clear_ticker_cache()
        response['ticker_cache_cleared'] = success
        
    return jsonify(response)

@app.route('/api/portfolio/analyze', methods=['POST'])
def analyze_portfolio_endpoint():
    data = request.json or {}
    tickers = data.get('tickers', [])
    if not tickers:
        return jsonify({'status': 'error', 'message': 'No se proporcionaron tickers'}), 400
        
    results = analyze_portfolio(tickers)
    return jsonify({'status': 'ok', 'results': results})

@app.route('/api/portfolio/config', methods=['GET', 'POST'])
def portfolio_config():
    config = config_mgr.get_config()
    if request.method == 'POST':
        data = request.json or {}
        tickers = data.get('tickers', [])
        config['portfolio'] = tickers
        config_mgr.save_config(config)
        return jsonify({'status': 'ok', 'message': 'Portafolio actualizado'})
    
    return jsonify({
        'tickers': config.get('portfolio', [])
    })

if __name__ == '__main__':
    print("🚀 Iniciando VISOR Web Server en http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
