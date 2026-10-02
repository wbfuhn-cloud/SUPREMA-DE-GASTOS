import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from signal_fusion import FusionInput, VALID_STATES, calibration_by_band, fuse_signal  # noqa: E402


def base_input(**changes):
    values = dict(
        symbol="TEST", horizon="5-20", heuristic_score=0.45, heuristic_state="COMPRAR",
        data_quality=0.99, regime="alcista", price=100.0, atr=2.0,
        calibrated_prob_up=0.72, calibrated_prob_down=0.15, model_approved=True,
        expected_return=0.04,
    )
    values.update(changes)
    return FusionInput(**values)


class Phase7IntegrationTests(unittest.TestCase):
    def test_coherence_and_mandatory_abstention(self):
        for quality in (0.40, 0.94, 0.95, 1.0):
            for ood in (False, True):
                result = fuse_signal(base_input(data_quality=quality, ml_ood=ood))
                self.assertIn(result["state"], VALID_STATES)
                self.assertFalse(isinstance(result["state"], (list, tuple, set)))
                if quality < 0.95 or ood:
                    self.assertEqual(result["state"], "SIN SEÑAL")

    def test_buy_has_complete_risk_explanation_and_is_reproducible(self):
        request = base_input()
        first = fuse_signal(request)
        second = fuse_signal(request)
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "COMPRAR")
        self.assertTrue(first["factors_for"] and first["factors_against"] and first["invalidation_triggers"])
        self.assertEqual(
            set(first["risk_plan"]),
            {"position_size_shares", "entry_price", "stop_price", "maximum_loss",
             "risk_budget", "risk_pct", "horizon"},
        )
        self.assertLessEqual(first["risk_plan"]["maximum_loss"], request.capital * 0.01)
        self.assertFalse(first["spectral_used"])
        scanner = (ROOT / "tools" / "NOTIFICADOR_BOT" / "stock_scanner.py").read_text(encoding="utf-8")
        ui = (ROOT / "tools" / "NOTIFICADOR_BOT" / "app.js").read_text(encoding="utf-8")
        self.assertIn("'Fusion_Horizons':", scanner)
        self.assertIn("Veredicto fusionado", ui)

    def test_calibration_bands_and_exit_are_independent_from_buy(self):
        observations = [(0.62, 1)] * 12 + [(0.62, 0)] * 8 + [(0.80, 1)] * 16 + [(0.80, 0)] * 4
        self.assertTrue(calibration_by_band(observations)["all_within_5pp"])
        result = fuse_signal(base_input(has_position=True, calibrated_prob_down=0.65))
        self.assertEqual(result["state"], "SALIR")
        self.assertIsNone(result["risk_plan"])
        self.assertIn("probabilidad calibrada de caída", " ".join(result["factors_against"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
