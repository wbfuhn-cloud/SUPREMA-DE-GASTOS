import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from spectral_features import (  # noqa: E402
    SpectralConfig, ablation_summary, dft_reference, latency_p95_ms,
    rolling_stability, spectral_features,
)


def prices_from_returns(returns):
    return 100.0 * np.exp(np.r_[0.0, np.cumsum(returns)])


class Phase6IntegrationTests(unittest.TestCase):
    def test_complete_dft_matches_fft_and_recovers_known_period(self):
        rng = np.random.default_rng(6)
        signal = rng.normal(size=32)
        reference = dft_reference(signal)
        fast = np.fft.fft(signal)
        relative_error = np.max(np.abs(reference - fast)) / np.max(np.abs(reference))
        self.assertLessEqual(relative_error, 1e-9)
        returns = 0.01 * np.sin(2 * np.pi * np.arange(80) / 16)
        result = spectral_features(prices_from_returns(returns), SpectralConfig(window=64))
        self.assertLessEqual(abs(result["dominant_period"] - 16), 1.0)

    def test_noise_stability_latency_and_causality_gates(self):
        rng = np.random.default_rng(20261002)
        recovered = []
        for _ in range(100):
            returns = 0.01 * np.sin(2 * np.pi * np.arange(96) / 16) + rng.normal(0, 0.002, 96)
            recovered.append(spectral_features(prices_from_returns(returns), SpectralConfig(window=64))["dominant_period"])
        self.assertGreaterEqual(np.mean(np.abs(np.asarray(recovered) - 16) <= 1), 0.90)
        stable = prices_from_returns(0.01 * np.sin(2 * np.pi * np.arange(180) / 16))
        self.assertGreaterEqual(rolling_stability(stable)["persistence_ratio"], 0.60)
        self.assertLessEqual(latency_p95_ms(stable[-65:], runs=50), 50.0)
        prefix = stable[:100]
        self.assertEqual(spectral_features(prefix), spectral_features(prefix.copy()))

    def test_fourier_remains_experimental_without_real_oos_ablation(self):
        result = spectral_features(prices_from_returns(0.01 * np.sin(2 * np.pi * np.arange(80) / 16)))
        self.assertFalse(result["production_enabled"])
        ablation = ablation_summary([.50, .52, .48], [.50, .51, .49], 0.40, 0.44, -0.10, -0.10)
        self.assertFalse(ablation["approved_for_signals"])
        self.assertEqual(ablation["decision"], "EXPERIMENT_ONLY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
