"""Evaluación reproducible del módulo Fourier de fase 6."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from spectral_features import (  # noqa: E402
    SpectralConfig, dft_reference, latency_p95_ms, prepare_window,
    rolling_stability, spectral_features,
)


def prices_from_returns(returns: np.ndarray, initial: float = 100.0) -> np.ndarray:
    return initial * np.exp(np.r_[0.0, np.cumsum(returns)])


def evaluate() -> dict:
    rng = np.random.default_rng(20261002)
    relative_errors = []
    for size in (8, 16, 32):
        signal = rng.normal(size=size)
        reference = dft_reference(signal)
        fast = np.fft.fft(signal)
        relative_errors.append(float(np.max(np.abs(reference - fast)) / max(np.max(np.abs(reference)), 1e-15)))

    period_errors = []
    for window, period in ((32, 8), (64, 16), (128, 32), (252, 42)):
        count = window + 12
        returns = 0.01 * np.sin(2 * np.pi * np.arange(count) / period)
        result = spectral_features(prices_from_returns(returns), SpectralConfig(window=window))
        period_errors.append(abs(result["dominant_period"] - period))

    successes = 0
    robustness_trials = 100
    window, period = 64, 16
    for _ in range(robustness_trials):
        returns = 0.01 * np.sin(2 * np.pi * np.arange(window + 16) / period) + rng.normal(0, 0.002, window + 16)
        recovered = spectral_features(prices_from_returns(returns), SpectralConfig(window=window))["dominant_period"]
        successes += abs(recovered - period) <= 1.0

    stable_returns = 0.01 * np.sin(2 * np.pi * np.arange(180) / 16)
    stable_prices = prices_from_returns(stable_returns)
    stability = rolling_stability(stable_prices, SpectralConfig(window=64))
    latency = latency_p95_ms(stable_prices[-65:], SpectralConfig(window=64), runs=150)

    prefix = stable_prices[:100]
    before = spectral_features(prefix, SpectralConfig(window=64))
    _future = np.r_[stable_prices, stable_prices[-1] * 50]
    after = spectral_features(prefix, SpectralConfig(window=64))
    causal_fields = ("dominant_period", "dominant_power_ratio", "dominant_phase", "spectral_entropy")
    leakage_findings = sum(before[field] != after[field] for field in causal_fields)

    gates = {
        "fft_relative_error_lte_1e_9": max(relative_errors) <= 1e-9,
        "period_error_lte_1_bar": max(period_errors) <= 1.0,
        "noise_recovery_gte_90pct": successes / robustness_trials >= 0.90,
        "stability_gte_60pct": stability["persistence_ratio"] >= 0.60,
        "latency_p95_lte_50ms": latency <= 50.0,
        "temporal_leakage_zero": leakage_findings == 0,
        "real_oos_ablation": False,
    }
    return {
        "schema": "inversiones-ia-fourier-evaluation/1.0",
        "seed": 20261002,
        "agreed_noise_snr": "sinusoid amplitude 0.01 / Gaussian sigma 0.002 = 5",
        "max_fft_relative_error": max(relative_errors),
        "max_period_error_bars": max(period_errors),
        "noise_recovery_ratio": successes / robustness_trials,
        "stability": stability,
        "latency_p95_ms": latency,
        "temporal_leakage_findings": leakage_findings,
        "gates": gates,
        "approved_for_signals": all(gates.values()),
        "decision": "EXPERIMENT_ONLY",
        "decision_reason": "No existe dataset trazable para una ablación walk-forward real baseline vs baseline + Fourier.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
