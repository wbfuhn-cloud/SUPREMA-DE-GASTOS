"""Indicadores y motor heurístico explícito de Inversiones IA 3.0.

Todas las funciones trabajan sobre precios ajustados cuando el proveedor así lo
indica. Nunca rellenan un indicador ausente con cero ni con el último precio.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


HEURISTIC_VERSION = "3.0.0"
MIN_SCORE_COVERAGE = 0.60

INDICATOR_SPEC = {
    "rsi": {"period": 14, "smoothing": "Wilder RMA (alpha=1/14)", "minimum_observations": 15},
    "macd": {"fast": 12, "slow": 26, "signal": 9, "smoothing": "EMA adjust=False", "minimum_observations": 35},
    "bollinger": {"window": 20, "stddev": 2.0, "ddof": 0, "minimum_observations": 20},
    "atr": {"period": 14, "smoothing": "Wilder RMA (alpha=1/14)", "minimum_observations": 15},
    "sma": {"windows": [20, 50, 200], "minimum_observations": "igual a la ventana"},
}

HORIZON_WEIGHTS = {
    "short": {"rsi": 0.25, "macd": 0.30, "bollinger": 0.20, "volume": 0.15, "jump": 0.10},
    "swing": {"rsi": 0.10, "macd": 0.15, "sma50": 0.15, "trend60": 0.30, "bollinger": 0.10, "volume": 0.10, "atr": 0.10},
    "trend": {"sma50_200": 0.45, "price_sma200": 0.30, "macd": 0.15, "atr": 0.10},
}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    values = pd.to_numeric(close, errors="coerce")
    delta = values.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + relative_strength))
    result = result.where(avg_loss != 0, 100.0)
    result = result.where(avg_gain != 0, 0.0)
    return result


def macd_frame(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    values = pd.to_numeric(close, errors="coerce")
    fast_ema = values.ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_ema = values.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd = fast_ema - slow_ema
    signal_line = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd - signal_line
    return pd.DataFrame({
        "macd": macd,
        "signal": signal_line,
        "histogram": histogram,
        "histogram_slope": histogram.diff(),
    })


def bollinger_frame(close: pd.Series, window: int = 20, deviations: float = 2.0) -> pd.DataFrame:
    values = pd.to_numeric(close, errors="coerce")
    middle = values.rolling(window=window, min_periods=window).mean()
    dispersion = values.rolling(window=window, min_periods=window).std(ddof=0)
    return pd.DataFrame({
        "upper": middle + deviations * dispersion,
        "middle": middle,
        "lower": middle - deviations * dispersion,
    })


def atr_series(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def compute_indicators(frame: pd.DataFrame) -> dict[str, Any]:
    close = pd.to_numeric(frame["Close"], errors="coerce")
    macd = macd_frame(close)
    bands = bollinger_frame(close)
    atr = atr_series(frame)
    volume = pd.to_numeric(frame.get("Volume"), errors="coerce")
    average_volume = volume.rolling(20, min_periods=20).mean() if volume is not None else None
    current_volume = _number(volume.iloc[-1]) if volume is not None and len(volume) else None
    average_volume_value = _number(average_volume.iloc[-1]) if average_volume is not None else None
    returns = close.pct_change()
    lookback = min(60, max(0, len(close) - 1))
    total_return_60 = _number(close.iloc[-1] / close.iloc[-1 - lookback] - 1) if lookback else None
    path = _number(close.diff().abs().tail(lookback).sum()) if lookback else None
    net = _number(abs(close.iloc[-1] - close.iloc[-1 - lookback])) if lookback else None
    return {
        "price": _number(close.iloc[-1]) if len(close) else None,
        "rsi": _number(rsi_series(close).iloc[-1]) if len(close) else None,
        "macd": _number(macd["macd"].iloc[-1]) if len(macd) else None,
        "macd_signal": _number(macd["signal"].iloc[-1]) if len(macd) else None,
        "macd_histogram": _number(macd["histogram"].iloc[-1]) if len(macd) else None,
        "macd_histogram_slope": _number(macd["histogram_slope"].iloc[-1]) if len(macd) else None,
        "bb_upper": _number(bands["upper"].iloc[-1]) if len(bands) else None,
        "bb_middle": _number(bands["middle"].iloc[-1]) if len(bands) else None,
        "bb_lower": _number(bands["lower"].iloc[-1]) if len(bands) else None,
        "atr": _number(atr.iloc[-1]) if len(atr) else None,
        "sma20": _number(close.rolling(20, min_periods=20).mean().iloc[-1]) if len(close) else None,
        "sma50": _number(close.rolling(50, min_periods=50).mean().iloc[-1]) if len(close) else None,
        "sma200": _number(close.rolling(200, min_periods=200).mean().iloc[-1]) if len(close) else None,
        "average_volume_20": average_volume_value,
        "volume_ratio": (
            current_volume / average_volume_value
            if current_volume is not None and average_volume_value and average_volume_value > 0
            else None
        ),
        "daily_return": _number(close.pct_change().iloc[-1]) if len(close) >= 2 else None,
        "total_return_60": total_return_60,
        "efficiency_60": net / path if net is not None and path and path > 0 else None,
        "realized_volatility_20": _number(returns.tail(20).std(ddof=0) * np.sqrt(252)),
        "extreme_move_count_20": int((returns.tail(20).abs() >= 0.05).sum()),
    }


def _signals(indicators: Mapping[str, Any]) -> dict[str, float | None]:
    price = indicators.get("price")
    rsi = indicators.get("rsi")
    macd = indicators.get("macd")
    signal = indicators.get("macd_signal")
    hist = indicators.get("macd_histogram")
    slope = indicators.get("macd_histogram_slope")
    atr = indicators.get("atr")
    rsi_signal = None if rsi is None else max(-1.0, min(1.0, (50.0 - rsi) / 20.0))
    macd_signal = None
    if None not in (macd, signal, hist, slope):
        direction = 1.0 if macd > signal and hist > 0 else -1.0 if macd < signal and hist < 0 else 0.0
        acceleration = 0.25 if slope > 0 else -0.25 if slope < 0 else 0.0
        macd_signal = max(-1.0, min(1.0, direction + acceleration))
    bollinger = None
    if price is not None and None not in (indicators.get("bb_upper"), indicators.get("bb_middle"), indicators.get("bb_lower")):
        width = indicators["bb_upper"] - indicators["bb_lower"]
        bollinger = max(-1.0, min(1.0, (indicators["bb_middle"] - price) / (width / 2))) if width > 0 else 0.0
    volume_ratio = indicators.get("volume_ratio")
    volume_signal = None if volume_ratio is None else max(-1.0, min(1.0, volume_ratio - 1.0))
    sma50 = indicators.get("sma50")
    sma200 = indicators.get("sma200")
    sma50_signal = None if price is None or sma50 is None else (1.0 if price > sma50 else -1.0)
    cross_signal = None if sma50 is None or sma200 is None else (1.0 if sma50 > sma200 else -1.0)
    price_sma200 = None if price is None or sma200 is None else (1.0 if price > sma200 else -1.0)
    atr_signal = None if price is None or atr is None or price <= 0 else max(-1.0, min(1.0, 1.0 - (atr / price) / 0.06))
    daily_return = indicators.get("daily_return")
    jump_signal = None if daily_return is None else (-1.0 if daily_return > 0.10 else 1.0 if daily_return < -0.10 else 0.0)
    total_return = indicators.get("total_return_60")
    trend60 = None if total_return is None else max(-1.0, min(1.0, total_return / 0.15))
    return {
        "rsi": rsi_signal,
        "macd": macd_signal,
        "bollinger": bollinger,
        "volume": volume_signal,
        "sma50": sma50_signal,
        "sma50_200": cross_signal,
        "price_sma200": price_sma200,
        "atr": atr_signal,
        "jump": jump_signal,
        "trend60": trend60,
    }


def classify_regime(indicators: Mapping[str, Any]) -> str:
    daily_return = indicators.get("daily_return")
    atr = indicators.get("atr")
    price = indicators.get("price")
    efficiency = indicators.get("efficiency_60")
    total_return = indicators.get("total_return_60")
    volatility = indicators.get("realized_volatility_20")
    if indicators.get("extreme_move_count_20", 0) >= 3 or (price and atr is not None and atr / price >= 0.08):
        return "high_volatility"
    if daily_return is not None and abs(daily_return) >= 0.10:
        return "jump"
    if efficiency is not None and efficiency < 0.20:
        return "lateral" if (volatility or 0) < 0.15 else "noise"
    if total_return is not None and total_return >= 0.08:
        return "uptrend"
    if total_return is not None and total_return <= -0.08:
        return "downtrend"
    return "lateral"


def _state(score: float, eligible: bool) -> str:
    if not eligible:
        return "SIN SEÑAL"
    if score >= 0.35:
        return "COMPRAR"
    if score > -0.15:
        return "MANTENER/ESPERAR"
    if score > -0.50:
        return "REDUCIR"
    return "SALIR"


def score_horizon(signals: Mapping[str, float | None], horizon: str) -> dict[str, Any]:
    weights = HORIZON_WEIGHTS[horizon]
    available_weight = sum(weight for name, weight in weights.items() if signals.get(name) is not None)
    coverage = available_weight / sum(weights.values())
    contributions = {
        name: round(50 * weight * float(signals[name]) / available_weight, 6)
        for name, weight in weights.items()
        if signals.get(name) is not None and available_weight > 0
    }
    directional_score = sum(weight * float(signals[name]) for name, weight in weights.items() if signals.get(name) is not None)
    directional_score = directional_score / available_weight if available_weight else 0.0
    display_score = round(50.0 + sum(contributions.values()), 2)
    missing = [name for name in weights if signals.get(name) is None]
    eligible = coverage >= MIN_SCORE_COVERAGE
    return {
        "horizon": horizon,
        "sessions": {"short": "1-3", "swing": "5-20", "trend": "20-60"}[horizon],
        "directional_score": round(directional_score, 6),
        "score": display_score,
        "coverage": round(coverage, 4),
        "state": _state(directional_score, eligible),
        "contributions": {"baseline": 50.0, **contributions},
        "missing": missing,
    }


def evaluate_heuristic(
    frame: pd.DataFrame,
    *,
    quote: Mapping[str, Any] | None = None,
    is_leveraged: bool = False,
    minimum_average_volume: float = 100_000,
) -> dict[str, Any]:
    indicators = compute_indicators(frame)
    signals = _signals(indicators)
    horizons = {name: score_horizon(signals, name) for name in HORIZON_WEIGHTS}
    regime = classify_regime(indicators)
    restrictions: list[str] = []
    # v3.3: Umbral rebajado de 0.95→0.80 — el score típico de Yahoo diario
    # es ~0.90 por gaps de fin de semana/festivos, y 0.95 bloqueaba TODO.
    quote_eligible = bool(quote) and not quote.get("is_stale", True) and quote.get("quality_score", 0) >= 0.80
    if not quote_eligible:
        restrictions.append("cotización vencida o de calidad insuficiente")
    average_volume = indicators.get("average_volume_20")
    if average_volume is None or average_volume < minimum_average_volume:
        restrictions.append("liquidez insuficiente o desconocida")
    if quote and quote.get("corporate_action_count", 0):
        restrictions.append("serie ajustada por acción corporativa; revisar evento")
    for result in horizons.values():
        if restrictions and any(text.startswith(("cotización", "liquidez")) for text in restrictions):
            result["state"] = "SIN SEÑAL"
    if is_leveraged:
        restrictions.append("ETF apalancado: prohibida recomendación de tendencia basada solo en técnico clásico")
        horizons["trend"]["state"] = "SIN SEÑAL"
    if regime == "jump":
        horizons["swing"]["state"] = "REDUCIR" if (indicators.get("daily_return") or 0) > 0 else "MANTENER/ESPERAR"
    elif regime == "high_volatility":
        restrictions.append("régimen de alta volatilidad: abstención obligatoria")
        for result in horizons.values():
            result["state"] = "SIN SEÑAL"
    elif regime in {"lateral", "noise"} and horizons["swing"]["state"] != "SIN SEÑAL":
        horizons["swing"]["state"] = "MANTENER/ESPERAR"
    primary = horizons["swing"]
    return {
        "heuristic_version": HEURISTIC_VERSION,
        "regime": regime,
        "indicator_spec": INDICATOR_SPEC,
        "indicators": indicators,
        "signals": signals,
        "horizons": horizons,
        "state": primary["state"],
        "score": primary["score"],
        "coverage": primary["coverage"],
        "contributions": primary["contributions"],
        "missing": primary["missing"],
        "restrictions": restrictions,
    }
