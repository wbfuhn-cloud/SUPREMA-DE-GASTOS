import tempfile
import unittest
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from adaptive_paper_experiment import AdaptivePaperExperiment


def candidate(price=100.0):
    return {
        "Ticker": "TEST", "Price": price, "Score": 75,
        "Data_Quality": 0.90, "Is_Leveraged": False, "Vol_Ratio": 1.5,
        "Realized_Volatility_20d_Pct": 45,
        "Historical_Coverage": {"eligible": True},
        "Holding_Outlook": {"horizons": {
            "1_month": {"sessions": 21, "historical_momentum_pct": 12,
                         "estimated_move_1sigma_pct": 18},
            "3_months": {"sessions": 63, "historical_momentum_pct": 20,
                          "estimated_move_1sigma_pct": 30},
            "6_months": {"sessions": 126, "historical_momentum_pct": 25,
                          "estimated_move_1sigma_pct": 45},
        }},
    }


class AdaptivePaperExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.experiment = AdaptivePaperExperiment(Path(self.temp.name) / "experiment.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_opens_only_a_simulated_position_and_persists_horizon(self):
        state = self.experiment.run_cycle([candidate()], date(2026, 10, 2))
        self.assertEqual(state["event"], "OPENED")
        self.assertEqual(state["mode"], "paper_only")
        self.assertFalse(state["real_money"])
        self.assertIn(state["open_position"]["horizon_sessions"], {21, 63, 126})

    def test_take_profit_closes_and_updates_bounded_experimental_weights(self):
        first = self.experiment.run_cycle([candidate()], date(2026, 10, 2))
        old = first["weights"]
        second = self.experiment.run_cycle([candidate(131.0)], date(2026, 10, 5))
        self.assertEqual(second["event"], "CLOSED_AND_LEARNED")
        self.assertEqual(second["closed_positions"], 1)
        self.assertEqual(second["wins"], 1)
        self.assertGreater(second["parameter_version"], first["parameter_version"])
        self.assertTrue(all(0.5 <= value <= 1.5 for value in second["weights"].values()))
        self.assertTrue(any(second["weights"][name] > old[name] for name in old))

    def test_cloud_backup_restores_position_without_starting_from_zero(self):
        original = self.experiment.run_cycle([candidate()], date(2026, 10, 2))
        backup = self.experiment.export_backup()
        second_path = Path(self.temp.name) / "restored.db"
        restored = AdaptivePaperExperiment(second_path)
        self.assertTrue(restored.restore_backup(backup))
        state = restored.status()
        self.assertEqual(state["open_position"]["position_id"], original["open_position"]["position_id"])
        self.assertEqual(state["parameter_version"], original["parameter_version"])


if __name__ == "__main__":
    unittest.main()
