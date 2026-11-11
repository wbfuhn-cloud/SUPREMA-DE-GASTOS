"""Regla canónica del Cazador de Gemas, compartida por API y Telegram."""

from __future__ import annotations

from typing import Any, Iterable
import math


def is_daily_gem(row: dict[str, Any]) -> bool:
    """Una gema es un breakout observable; no implica compra automática."""
    if bool(row.get("Is_Leveraged")):
        return False
    if row.get("Signal_Eligible") is not True:
        return False
    state = str(row.get("Signal_State") or row.get("Viabilidad") or "").upper()
    if state in {"SIN SEÑAL", "SALIR", "REDUCIR"}:
        return False
    try:
        volume_ratio = float(row.get("Vol_Ratio") or 0)
        rsi = float(row.get("RSI"))
        macd = float(row.get("MACD") or 0)
        macd_signal = float(row['MACD_Signal']) if row.get('MACD_Signal') is not None else macd
        macd_hist = float(row.get("MACD_Hist") or 0)
        market_cap = float(row.get("Market_Cap") or 0)
    except (TypeError, ValueError):
        return False
    return (
        all(math.isfinite(value) for value in (volume_ratio, rsi, macd, macd_signal, macd_hist, market_cap))
        and volume_ratio >= 1.1
        and (macd > macd_signal or macd_hist > 0 or macd > 0)
        and 30 <= rsi < 68
        and 0 < market_cap < 200_000_000_000
    )


def select_daily_gems(results: Iterable[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    selected = [dict(row) for row in results if is_daily_gem(row)]
    selected.sort(key=lambda row: float(row.get("Vol_Ratio") or 0), reverse=True)
    return selected[:max(0, int(limit))]
