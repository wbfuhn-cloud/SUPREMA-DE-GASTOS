import os
import sys
import json
import argparse
from datetime import datetime

# Agregar el directorio del script al path para encontrar módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from portfolio_analyzer import analyze_ticker_strategy, analyze_portfolio
    import yfinance as yf
except ImportError:
    print("Error: No se pudieron importar los módulos de análisis.")
    sys.exit(1)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'visor_config.json')

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {"watchlist": [], "portfolio": []}

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)

def get_summary(tickers):
    if not tickers:
        return "No hay acciones para analizar."
    
    print(f"🔍 Analizando {len(tickers)} acciones...")
    results = analyze_portfolio(tickers)
    
    summary = []
    summary.append(f"📅 *RESUMEN DE MERCADO - {datetime.now().strftime('%d/%m/%Y %H:%M')}*")
    summary.append("="*40)
    
    for res in results:
        if "error" in res and res["error"]:
            summary.append(f"❌ *{res['ticker']}*: Error - {res['error']}")
            continue
            
        emoji_verdict = res['verdict']
        summary.append(f"🔹 *{res['ticker']}* | Price: ${res['price']} (${res.get('price_mxn', 0)} MXN)")
        summary.append(f"   Status: {emoji_verdict}")
        summary.append(f"   RSI: {res['rsi']}")
        if res['reasons']:
            summary.append(f"   Razones: {', '.join(res['reasons'])}")
        summary.append("-" * 20)
    
    return "\n".join(summary)

def main():
    parser = argparse.ArgumentParser(description="Bot Notificador de Inversiones (Terminal CLI)")
    parser.add_argument('--scan', type=str, help="Escanear tickers específicos separados por coma (ej: TSLA,AAPL)")
    parser.add_argument('--portfolio', action='store_true', help="Analizar mi portafolio actual")
    parser.add_argument('--add', type=str, help="Agregar una acción a mi portafolio")
    parser.add_argument('--remove', type=str, help="Quitar una acción de mi portafolio")
    parser.add_argument('--list', action='store_true', help="Listar acciones en mi portafolio")

    args = parser.parse_args()
    config = load_config()
    
    # Asegurar que existe la clave 'portfolio'
    if 'portfolio' not in config:
        config['portfolio'] = []

    if args.add:
        ticker = args.add.upper().strip()
        if ticker not in config['portfolio']:
            config['portfolio'].append(ticker)
            save_config(config)
            print(f"✅ {ticker} agregado al portafolio.")
        else:
            print(f"ℹ️ {ticker} ya está en el portafolio.")
            
    elif args.remove:
        ticker = args.remove.upper().strip()
        if ticker in config['portfolio']:
            config['portfolio'].remove(ticker)
            save_config(config)
            print(f"🗑️ {ticker} eliminado del portafolio.")
        else:
            print(f"❌ {ticker} no está en el portafolio.")

    elif args.list:
        if config['portfolio']:
            print("📋 Acciones en Portafolio:", ", ".join(config['portfolio']))
        else:
            print("Empty portfolio.")

    elif args.scan:
        tickers = [t.strip().upper() for t in args.scan.split(',')]
        print(get_summary(tickers))

    elif args.portfolio:
        if not config['portfolio']:
            print("⚠️ El portafolio está vacío. Usa --add para agregar acciones.")
        else:
            print(get_summary(config['portfolio']))
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
