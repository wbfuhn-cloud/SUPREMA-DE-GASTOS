"""
portfolio_analyzer.py — Analiza tickers del portafolio con veredicto claro.
Usa la API directa de Yahoo v8 (sin yfinance) para evitar errores 401.
"""
from pathlib import Path
import os
import pandas as pd

from stock_scanner import (
    _fetch_history_raw, _fetch_quote_batch, _SESSION,
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    _get_usd_mxn, LEVERAGED_ETFS
)


def _is_leveraged_etf(ticker: str) -> bool:
    return ticker.upper() in LEVERAGED_ETFS


def analyze_ticker_strategy(ticker_symbol: str, entry_price: float = 0, qty: float = 0) -> dict:
    """Análisis técnico completo con veredicto de acción para un ticker."""
    try:
        df = _fetch_history_raw(ticker_symbol, period='1y')

        if df is None or len(df) < 50:
            return {"ticker": ticker_symbol, "error": "Sin datos históricos suficientes"}

        close  = df['Close'].dropna()
        price  = float(close.iloc[-1])
        rsi    = calculate_rsi(close)
        macd, signal, hist = calculate_macd(close)
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(close)
        sma50  = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50  else price
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price

        buy_signals = 0.0
        reasons     = []

        # Cálculo de Ganancia/Pérdida si hay precio de entrada
        pl_pct = 0
        if entry_price > 0:
            pl_pct = ((price / entry_price) - 1) * 100
            if pl_pct > 0:
                reasons.append(f"💰 Ganancia actual: +{pl_pct:.1f}%")
                if pl_pct > 15: buy_signals -= 0.5 # Incentivo a tomar ganancias
            else:
                reasons.append(f"🔻 Pérdida actual: {pl_pct:.1f}%")
                if pl_pct < -10: buy_signals -= 1 # Alerta de stop loss psicológico

        # RSI
        if ticker_symbol.upper() == 'TSLA':
            if rsi < 30:
                buy_signals += 1; reasons.append(f"✅ RSI sobreventa extrema ({rsi:.1f})")
            elif rsi > 70:
                buy_signals -= 1; reasons.append(f"⚠️ RSI sobrecompra ({rsi:.1f})")
        else:
            if rsi < 40:
                buy_signals += 1; reasons.append(f"✅ RSI bajo — oportunidad ({rsi:.1f})")
            elif rsi > 65:
                buy_signals -= 1; reasons.append(f"⚠️ RSI alto ({rsi:.1f})")

        # Bollinger Bands
        if bb_lower > 0 and price < bb_lower:
            buy_signals += 1; reasons.append("✅ Precio bajo Banda Bollinger Inferior")
        elif bb_upper > 0 and price > bb_upper:
            buy_signals -= 1; reasons.append("⚠️ Precio sobre Banda Bollinger Superior")

        # SMA 200
        if not pd.isna(sma200):
            if abs(price - sma200) / sma200 < 0.05 and price > sma200:
                buy_signals += 1; reasons.append("✅ Rebote en soporte SMA 200")
            elif price < sma200:
                buy_signals -= 0.5; reasons.append("⚠️ Tendencia bajista (precio < SMA 200)")

        # MACD
        if macd > signal and hist > 0:
            buy_signals += 0.5; reasons.append("✅ MACD alcista confirmado")
        elif macd < signal and hist < 0:
            buy_signals -= 0.5; reasons.append("⚠️ MACD bajista confirmado")

        # Veredicto final
        if _is_leveraged_etf(ticker_symbol):
            # Los ETFs apalancados NUNCA deben recibir senal de COMPRA
            # Su decaimiento estructural hace que cualquier posicion larga pierda con el tiempo
            if buy_signals >= 0.5 and buy_signals < 2:
                verdict = "MEDIA SENIAL (ETP apalancado - NO recomendado)"
                buy_signals = 0  # neutralizar
            elif buy_signals >= 2:
                verdict = "EVITAR (ETF apalancado - decaimiento estructural)"
                buy_signals = -0.5  # forzar venta parcial
            elif buy_signals >= 0:  # entre 0 y 0.5
                verdict = "MANTEN con stop-loss (ETP apalancado)"
            else:
                verdict = "REDUCIR o VENDER (para ETFs apalancados)"
        else:
            if buy_signals >= 2:
                verdict = "COMPRA / AUMENTA (Excelente oportunidad)"
            elif 0.5 <= buy_signals < 2:
                verdict = "MANTEN / ACUMULA (Aun tiene potencial)"
            elif -0.5 < buy_signals < 0.5:
                verdict = "MANTEN (Riesgo neutral)"
            elif -2 < buy_signals <= -0.5:
                if entry_price > 0 and pl_pct < 0:
                    verdict = "REDUCIR (Limita pérdidas/Reduce riesgo)"
                else:
                    verdict = "VENTA PARCIAL (Toma ganancias/Reduce riesgo)"
            else:
                verdict = "VENTA TOTAL (Alto riesgo de caida)"

        return {
            "ticker":       ticker_symbol,
            "price":        round(price, 2),
            "entry_price":  entry_price,
            "qty":          qty,
            "pl_pct":       round(pl_pct, 2),
            "rsi":          round(rsi, 2),
            "verdict":      verdict,
            "reasons":      reasons,
            "is_leveraged": _is_leveraged_etf(ticker_symbol),
            "error":        None
        }
    except Exception as e:
        return {"ticker": ticker_symbol, "error": str(e)}


def analyze_portfolio(portfolio_data) -> list:
    """
    Analiza el portafolio.
    portfolio_data puede ser una lista de tickers o un dict {TICKER: {qty, avg_price}}
    """
    from concurrent.futures import ThreadPoolExecutor
    exchange_rate = _get_usd_mxn()
    results = []
    tasks = []

    if isinstance(portfolio_data, dict):
        for t, info in portfolio_data.items():
            tasks.append((t.upper(), float(info.get('avg_price', 0)), float(info.get('qty', 0))))
    else:
        for t in portfolio_data:
            tasks.append((t.upper(), 0, 0))

    if not tasks: return []

    def _worker(task):
        return analyze_ticker_strategy(task[0], task[1], task[2])

    with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as ex:
        futures = list(ex.map(_worker, tasks))

    for res in futures:
        if res.get("error") is None:
            res["price_mxn"] = round(res["price"] * exchange_rate, 2)
            if res["entry_price"] > 0:
                res["pl_val"] = round((res["price"] - res["entry_price"]) * res["qty"], 2)
                res["pl_mxn"] = round(res["pl_val"] * exchange_rate, 2)
        results.append(res)

    return results


def get_portfolio_summary() -> str:
    """Genera resumen textual del portafolio para Telegram."""
    import json
    from datetime import datetime

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(root_dir, 'visor_config.json')

    portfolio = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                portfolio = config.get('portfolio', {})
                # Retrocompatibilidad si portfolio es una lista
                if isinstance(portfolio, list):
                    portfolio = {t: {'qty': 0, 'avg_price': 0} for t in portfolio}
        except: pass

    if not portfolio:
        return "⚠️ Tu portafolio real está vacío. Agrega acciones con su cantidad y precio en el panel web."

    results  = analyze_portfolio(portfolio)
    summary  = [f"📊 *REPORTE DE CARTERA* — {datetime.now().strftime('%d/%m %H:%M')}", "━━━━━━━━━━━━━━━━━━━━"]

    total_pl_usd = 0
    for res in results:
        if res.get("error"):
            summary.append(f"❌ *{res['ticker']}*: {res['error']}")
            continue
        
        pl_icon = "📈" if res['pl_pct'] >= 0 else "📉"
        pl_str = f"{pl_icon} {res['pl_pct']}%" if res['entry_price'] > 0 else ""
        
        summary.append(f"🔹 *{res['ticker']}* | ${res['price']} {pl_str}")
        summary.append(f"   {res['verdict']}")
        
        if res['entry_price'] > 0:
            total_pl_usd += res.get('pl_val', 0)
            summary.append(f"   Cant: {res['qty']} | P&L: ${res.get('pl_val', 0)} USD")
            
        if res['reasons']:
            # Solo mostrar las razones más importantes
            important_reasons = [r for r in res['reasons'] if '💰' not in r and '🔻' not in r]
            if important_reasons:
                summary.append(f"   💡 {', '.join(important_reasons[:2])}")
        summary.append("────────────────────")

    if total_pl_usd != 0:
        summary.append(f"💰 *BALANCE TOTAL:* ${total_pl_usd:,.2f} USD")

    return "\n".join(summary)
