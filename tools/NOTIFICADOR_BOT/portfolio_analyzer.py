"""
portfolio_analyzer.py — Analiza tickers del portafolio con veredicto claro.
Usa la API directa de Yahoo v8 (sin yfinance) para evitar errores 401.
"""
from pathlib import Path
import os
import math
import pandas as pd

from stock_scanner import (
    _fetch_history_raw, _fetch_quote_batch, _SESSION,
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    _get_usd_mxn, LEVERAGED_ETFS
)
from market_data import exchange_rate_contract, quote_from_history, ensure_quote_contract
from technical_engine import HEURISTIC_VERSION, evaluate_heuristic
from signal_fusion import FUSION_VERSION, FusionInput, fuse_signal
from portfolio_status import classify_portfolio_position


def _is_leveraged_etf(ticker: str) -> bool:
    return ticker.upper() in LEVERAGED_ETFS


def analyze_ticker_strategy(
    ticker_symbol: str,
    entry_price: float = 0,
    qty: float = 0,
    quote_override: dict | None = None,
) -> dict:
    """Análisis técnico completo con veredicto de acción para un ticker."""
    try:
        df = _fetch_history_raw(ticker_symbol, period='1y')
        if quote_override:
            if quote_override.get('symbol') != ticker_symbol.upper():
                raise ValueError('La cotización canónica no corresponde al ticker')
            quote_override = ensure_quote_contract({'Quote': quote_override})

        if df is None or len(df) < 50:
            if quote_override and quote_override.get("price") is not None:
                price = round(float(quote_override["price"]), 2)
                pl_pct = ((price / entry_price) - 1) * 100 if entry_price > 0 else None
                is_leveraged = _is_leveraged_etf(ticker_symbol)
                position_status = classify_portfolio_position(
                    pl_pct=pl_pct, signal_state="SIN SEÑAL", signal_eligible=False,
                    data_quality=float(quote_override.get("quality_score", 0.0)),
                    is_leveraged=is_leveraged,
                    quote_adjusted=bool(quote_override.get("adjusted", False)),
                    quote_stale=quote_override.get('is_stale', True),
                )
                return {
                    "ticker": ticker_symbol,
                    "price": price,
                    "entry_price": entry_price,
                    "qty": qty,
                    "pl_pct": round(pl_pct, 2) if pl_pct is not None else None,
                    "quote": dict(quote_override),
                    "data_quality": quote_override.get("quality_score", 0.0),
                    "signal_eligible": False,
                    "is_leveraged": is_leveraged,
                    "portfolio_status": position_status,
                    "pnl_reliable": position_status["pnl_reliable"],
                    "error": "Sin datos históricos suficientes para emitir veredicto",
                }
            position_status = classify_portfolio_position(
                pl_pct=None, signal_state="SIN SEÑAL", signal_eligible=False,
                data_quality=0.0, is_leveraged=_is_leveraged_etf(ticker_symbol),
                quote_adjusted=False,
            )
            return {"ticker": ticker_symbol, "entry_price": entry_price, "qty": qty,
                    "portfolio_status": position_status, "pnl_reliable": False,
                    "error": "Sin datos históricos suficientes"}

        close  = df['Close'].dropna()
        quote = quote_from_history(
            ticker_symbol,
            df,
            interval='1d',
            adjusted=bool(df.attrs.get('adjusted', False)),
        )
        if quote_override:
            if quote_override.get("symbol") != ticker_symbol.upper():
                raise ValueError("La cotización canónica no corresponde al ticker")
            quote = dict(quote_override)
        price  = float(quote["price"])
        weekly_change_pct = None
        if len(close) >= 6 and float(close.iloc[-6]) > 0:
            weekly_change_pct = ((price / float(close.iloc[-6])) - 1.0) * 100.0

        upside_scenario_3m_pct = None
        returns_3m = close.pct_change().dropna().tail(63)
        if len(returns_3m) >= 20:
            reference_index = max(0, len(close) - 64)
            reference_price = float(close.iloc[reference_index])
            momentum_3m = ((price / reference_price) - 1.0) * 100.0 if reference_price > 0 else 0.0
            volatility_3m = float(returns_3m.std()) * math.sqrt(63) * 100.0
            upside_scenario_3m_pct = min(40.0, max(0.0, momentum_3m) + max(0.0, volatility_3m))
        is_leveraged = _is_leveraged_etf(ticker_symbol)
        heuristic = evaluate_heuristic(df, quote=quote, is_leveraged=is_leveraged)
        rsi = heuristic["indicators"].get("rsi")
        reasons = [
            f"{name}: {value:+.2f} puntos"
            for name, value in heuristic["contributions"].items()
            if name != "baseline"
        ]
        reasons.extend(heuristic["restrictions"])

        # Cálculo de Ganancia/Pérdida si hay precio de entrada
        pl_pct = 0
        if entry_price > 0:
            pl_pct = ((price / entry_price) - 1) * 100
            if pl_pct > 0:
                reasons.append(f"💰 Ganancia actual: +{pl_pct:.1f}%")
                if pl_pct > 15:
                    reasons.append("Ganancia >15%: evaluar reducción de riesgo")
            else:
                reasons.append(f"🔻 Pérdida actual: {pl_pct:.1f}%")
                if pl_pct <= -15:
                    reasons.append("Pérdida de 15% o más: umbral de protección")

        regime_map = {
            'uptrend': 'alcista', 'lateral': 'lateral', 'noise': 'lateral',
            'downtrend': 'bajista', 'jump': 'crisis', 'high_volatility': 'crisis',
        }
        fusion = fuse_signal(FusionInput(
            symbol=ticker_symbol,
            horizon=heuristic['horizons']['swing']['sessions'],
            heuristic_score=float(heuristic['horizons']['swing']['directional_score']),
            heuristic_state=heuristic['state'],
            data_quality=float(quote.get('quality_score', 0.0)),
            regime=regime_map.get(heuristic['regime'], 'lateral'),
            price=price,
            atr=float(heuristic['indicators'].get('atr') or 0.0),
            has_position=entry_price > 0 and qty > 0,
            model_approved=False,
            stop_triggered=entry_price > 0 and pl_pct <= -15,
            profit_take_triggered=entry_price > 0 and pl_pct > 15,
            position_concentration=0.0,
            aggregate_open_risk=0.0,
            leveraged_etf=is_leveraged,
        ))
        verdict = fusion['state']
        reasons.extend(fusion['factors_for'])
        reasons.extend(fusion['factors_against'])
        position_status = classify_portfolio_position(
            pl_pct=pl_pct, signal_state=verdict,
            signal_eligible=verdict != "SIN SEÑAL",
            data_quality=float(quote.get('quality_score', 0.0)),
            is_leveraged=is_leveraged,
            quote_adjusted=bool(quote.get('adjusted', False)),
            weekly_change_pct=weekly_change_pct,
            trend_state=heuristic["horizons"]["trend"].get("state"),
            upside_scenario_3m_pct=upside_scenario_3m_pct,
            quote_stale=quote.get('is_stale', True),
        )

        return {
            "ticker":       ticker_symbol,
            "instrument_name": df.attrs.get('instrument_name') or ticker_symbol,
            "research_only": True,
            "price":        round(price, 2),
            "entry_price":  entry_price,
            "qty":          qty,
            "pl_pct":       round(pl_pct, 2),
            "weekly_change_pct": round(weekly_change_pct, 2) if weekly_change_pct is not None else None,
            "upside_scenario_3m_pct": round(upside_scenario_3m_pct, 2) if upside_scenario_3m_pct is not None else None,
            "rsi":          round(rsi, 2) if rsi is not None else None,
            "verdict":      verdict,
            "reasons":      reasons,
            "is_leveraged": is_leveraged,
            "heuristic_version": HEURISTIC_VERSION,
            "fusion_version": FUSION_VERSION,
            "fusion": fusion,
            "horizon_scores": heuristic["horizons"],
            "score": heuristic["score"],
            "score_contributions": heuristic["contributions"],
            "missing_indicators": heuristic["missing"],
            "quote":        quote,
            "data_quality": quote.get("quality_score", 0.0),
            "signal_eligible": verdict != "SIN SEÑAL",
            "portfolio_status": position_status,
            "pnl_reliable": position_status["pnl_reliable"],
            "error":        None
        }
    except Exception as e:
        return {"ticker": ticker_symbol, "error": str(e)}


def analyze_portfolio(portfolio_data, quote_overrides: dict | None = None) -> list:
    """
    Analiza el portafolio.
    portfolio_data puede ser una lista de tickers o un dict {TICKER: {qty, avg_price}}
    """
    from concurrent.futures import ThreadPoolExecutor
    exchange_rate = _get_usd_mxn()
    rate_meta = exchange_rate_contract(exchange_rate)
    quote_overrides = quote_overrides or {}
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
        return analyze_ticker_strategy(task[0], task[1], task[2], quote_overrides.get(task[0]))

    with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as ex:
        futures = list(ex.map(_worker, tasks))

    for res in futures:
        if res.get("price") is not None:
            res["price_mxn"] = round(res["price"] * exchange_rate, 2)
            res["exchange_rate"] = rate_meta
            if res["entry_price"] > 0:
                res["pl_val"] = round((res["price"] - res["entry_price"]) * res["qty"], 2)
                res["pl_mxn"] = round(res["pl_val"] * exchange_rate, 2)
        results.append(res)

    return results


def get_portfolio_summary(portfolio_data=None) -> str:
    """Genera resumen textual del portafolio para Telegram."""
    import json
    from datetime import datetime

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(root_dir, 'visor_config.json')

    portfolio = {} if portfolio_data is None else portfolio_data
    if portfolio_data is None and os.path.exists(config_path):
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
