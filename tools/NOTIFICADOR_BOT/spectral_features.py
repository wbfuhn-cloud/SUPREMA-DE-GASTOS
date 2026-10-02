"""Features Fourier causales para investigación; no genera señales operativas.

La implementación usa log-retornos estandarizados dentro de cada ventana, Hann y
la DFT completa. ``numpy.fft.rfft`` es solo el algoritmo rápido equivalente.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, asdict
from typing import Any, Iterable

import numpy as np


SPECTRAL_VERSION = "1.0.0-experimental"


@dataclass(frozen=True)
class SpectralConfig:
    window: int = 64
    short_band: tuple[float, float] = (2.0, 8.0)
    medium_band: tuple[float, float] = (8.0, 24.0)
    long_band: tuple[float, float] = (24.0, 64.0)
    max_components: int = 3
    stability_tolerance: float = 0.15


def log_returns(prices: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(prices), dtype=float)
    if values.ndim != 1 or len(values) < 3 or not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("Se requieren al menos 3 precios positivos y finitos")
    return np.diff(np.log(values))


def prepare_window(prices: Iterable[float], window: int) -> tuple[np.ndarray, np.ndarray, float, float]:
    returns = log_returns(prices)
    if len(returns) < window:
        raise ValueError(f"Se requieren {window + 1} precios para {window} retornos")
    returns = returns[-window:]
    mean = float(np.mean(returns))
    std = float(np.std(returns, ddof=0))
    if std <= 1e-15:
        raise ValueError("La ventana no tiene variación suficiente")
    standardized = (returns - mean) / std
    hann = np.hanning(window)
    return standardized * hann, hann, mean, std


def dft_reference(signal: Iterable[float]) -> np.ndarray:
    """DFT expandida Σx[n](cos - i·sin), usada como referencia matemática."""
    values = np.asarray(list(signal), dtype=float)
    count = len(values)
    output = np.empty(count, dtype=complex)
    for k in range(count):
        real = 0.0
        imaginary = 0.0
        for n, value in enumerate(values):
            angle = 2.0 * math.pi * k * n / count
            real += value * math.cos(angle)
            imaginary -= value * math.sin(angle)
        output[k] = complex(real, imaginary)
    return output


def _band_power(periods: np.ndarray, power: np.ndarray, bounds: tuple[float, float]) -> float:
    mask = (periods >= bounds[0]) & (periods < bounds[1])
    total = float(np.sum(power))
    return float(np.sum(power[mask]) / total) if total > 0 else 0.0


def _dominant_period_from_prepared(prepared: np.ndarray) -> tuple[float, int, np.ndarray, np.ndarray]:
    spectrum = np.fft.rfft(prepared)
    power = np.abs(spectrum) ** 2
    power[0] = 0.0
    dominant_index = int(np.argmax(power))
    period = len(prepared) / dominant_index if dominant_index else math.inf
    return float(period), dominant_index, spectrum, power


def reconstruct_future(prepared: np.ndarray, hann: np.ndarray, return_mean: float,
                       return_std: float, horizon: int,
                       max_components: int = 3) -> np.ndarray:
    """Reconstrucción limitada a K armónicos; nunca extrapola más de un ciclo."""
    count = len(prepared)
    spectrum = np.fft.rfft(prepared)
    candidates = np.argsort(np.abs(spectrum[1:]))[::-1][:max_components] + 1
    if not len(candidates):
        return np.full(horizon, return_mean)
    maximum_horizon = max(1, int(min(count / candidates)))
    horizon = min(int(horizon), maximum_horizon)
    points = np.arange(count, count + horizon, dtype=float)
    reconstruction = np.zeros(horizon, dtype=float)
    coherent_gain = max(float(np.sum(hann)), 1e-15)
    for index in candidates:
        amplitude = 2.0 * abs(spectrum[index]) / coherent_gain
        phase = float(np.angle(spectrum[index]))
        reconstruction += amplitude * np.cos(2.0 * np.pi * index * points / count + phase)
    return return_mean + return_std * reconstruction


def spectral_features(prices: Iterable[float], config: SpectralConfig = SpectralConfig()) -> dict[str, Any]:
    source = np.asarray(list(prices), dtype=float)
    prepared, hann, return_mean, return_std = prepare_window(source, config.window)
    period, dominant_index, spectrum, power = _dominant_period_from_prepared(prepared)
    psd = power / max(float(np.sum(hann ** 2)), 1e-15)
    usable_power = psd[1:]
    total_power = float(np.sum(usable_power))
    normalized = usable_power / total_power if total_power > 0 else np.zeros_like(usable_power)
    nonzero = normalized[normalized > 0]
    entropy = float(-np.sum(nonzero * np.log(nonzero)) / np.log(len(normalized))) if len(normalized) > 1 else 1.0
    dominant_share = float(psd[dominant_index] / total_power) if total_power > 0 else 0.0
    noise_power = max(total_power - float(psd[dominant_index]), 1e-15)
    periods = np.full(len(power), np.inf, dtype=float)
    periods[1:] = config.window / np.arange(1, len(power))

    phase = float(np.angle(spectrum[dominant_index]))
    future = reconstruct_future(prepared, hann, return_mean, return_std, 3, config.max_components)
    slope = float(future[0] - return_mean)
    curvature = float(future[2] - 2.0 * future[1] + future[0]) if len(future) >= 3 else 0.0

    previous_period = math.nan
    previous_phase = math.nan
    stability = 0.0
    if len(source) >= config.window + 2:
        previous, _window, _mean, _std = prepare_window(source[:-1], config.window)
        previous_period, previous_index, previous_spectrum, _previous_power = _dominant_period_from_prepared(previous)
        previous_phase = float(np.angle(previous_spectrum[previous_index]))
        relative_change = abs(period - previous_period) / max(period, previous_period)
        stability = max(0.0, 1.0 - relative_change / max(config.stability_tolerance, 1e-9))

    return {
        "spectral_version": SPECTRAL_VERSION,
        "config": asdict(config),
        "window_end_index": int(len(source) - 1),
        "dominant_period": period,
        "dominant_power_ratio": dominant_share,
        "dominant_psd": float(psd[dominant_index]),
        "total_psd": total_power,
        "short_band_power": _band_power(periods, psd, config.short_band),
        "medium_band_power": _band_power(periods, psd, config.medium_band),
        "long_band_power": _band_power(periods, psd, config.long_band),
        "spectral_entropy": entropy,
        "dominant_phase": phase,
        "phase_change": None if not math.isfinite(previous_phase) else float(np.angle(np.exp(1j * (phase - previous_phase)))),
        "cycle_stability": stability,
        "spectral_snr": float(psd[dominant_index] / noise_power),
        "reconstruction_slope": slope,
        "forecast_curvature": curvature,
        "distance_to_peak_radians": float(((-phase) % (2.0 * math.pi))),
        "production_enabled": False,
        "decision": "EXPERIMENT_ONLY",
    }


def spectral_candidate(features: dict[str, Any], *, data_quality: float, liquid: bool,
                       strong_bearish_trend: bool, expected_net_return: float,
                       costs_plus_margin: float, power_drop: float = 0.0,
                       abrupt_phase_change: bool = False) -> dict[str, Any]:
    """Hipótesis BUY/EXIT para backtest; nunca habilita una orden de producción."""
    reasons = []
    if data_quality < 0.95 or not liquid or features["spectral_entropy"] > 0.80 \
            or features["cycle_stability"] < 0.60:
        state = "NO_SIGNAL"
        reasons.append("calidad, liquidez, entropía o estabilidad insuficiente")
    elif power_drop >= 0.40 or abrupt_phase_change or features["reconstruction_slope"] < 0:
        state = "EXIT_CANDIDATE"
        reasons.append("pérdida de potencia, ruptura de fase o pendiente negativa")
    elif (features["reconstruction_slope"] > 0 and features["dominant_power_ratio"] >= 0.20
          and expected_net_return > costs_plus_margin and not strong_bearish_trend):
        state = "BUY_CANDIDATE"
        reasons.append("tramo ascendente estable con edge neto experimental")
    else:
        state = "NO_SIGNAL"
        reasons.append("condiciones espectrales incompletas")
    return {"candidate": state, "reasons": reasons, "production_enabled": False,
            "warning": "Solo investigación; no usar para operar."}


def rolling_stability(prices: Iterable[float], config: SpectralConfig = SpectralConfig()) -> dict[str, float]:
    values = np.asarray(list(prices), dtype=float)
    periods = []
    for end in range(config.window + 1, len(values) + 1):
        prepared, *_ = prepare_window(values[:end], config.window)
        period, *_ = _dominant_period_from_prepared(prepared)
        periods.append(period)
    if len(periods) < 2:
        return {"eligible_windows": float(len(periods)), "persistence_ratio": 0.0}
    stable = [abs(a - b) / max(a, b) <= config.stability_tolerance for a, b in zip(periods, periods[1:])]
    return {"eligible_windows": float(len(periods)), "persistence_ratio": float(np.mean(stable))}


def latency_p95_ms(prices: Iterable[float], config: SpectralConfig = SpectralConfig(), runs: int = 100) -> float:
    durations = []
    values = list(prices)
    for _ in range(runs):
        started = time.perf_counter()
        spectral_features(values, config)
        durations.append((time.perf_counter() - started) * 1000.0)
    return float(np.percentile(durations, 95))


def ablation_summary(baseline_precision: Iterable[float], fourier_precision: Iterable[float],
                     baseline_sharpe: float, fourier_sharpe: float,
                     baseline_drawdown: float, fourier_drawdown: float) -> dict[str, Any]:
    baseline = np.asarray(list(baseline_precision), dtype=float)
    enhanced = np.asarray(list(fourier_precision), dtype=float)
    if baseline.shape != enhanced.shape or not len(baseline):
        raise ValueError("Los folds baseline y Fourier deben corresponder uno a uno")
    improvements = enhanced - baseline
    precision_gain = float(np.mean(improvements))
    sharpe_gain = float(fourier_sharpe - baseline_sharpe)
    relative_drawdown_change = float(
        (abs(fourier_drawdown) - abs(baseline_drawdown)) / max(abs(baseline_drawdown), 1e-12)
    )
    approved = bool(
        (precision_gain >= 0.03 or sharpe_gain >= 0.15)
        and float(np.mean(improvements > 0)) >= 0.70
        and relative_drawdown_change <= 0.05
    )
    return {
        "precision_at_k_gain": precision_gain,
        "sharpe_gain": sharpe_gain,
        "positive_fold_ratio": float(np.mean(improvements > 0)),
        "relative_drawdown_change": relative_drawdown_change,
        "approved_for_signals": approved,
        "decision": "CANDIDATE" if approved else "EXPERIMENT_ONLY",
    }
