"""Pruebas autocontenidas para los criterios funcionales de la Fase 1."""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from ml_predictor import StockMLPredictor  # noqa: E402
from recommendation_learner import RecommendationDB  # noqa: E402


class LearnerConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "learner.db"
        self.db = RecommendationDB(str(self.db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_empty_history_is_unavailable_not_fifty_percent(self):
        result = self.db.get_confidence_for_ticker("TEST", "Technology", 50)
        self.assertFalse(result["available"])
        self.assertIsNone(result["confidence"])
        self.assertEqual(result["sample_size"], 0)

    def test_verified_history_produces_evidence_based_confidence(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO recommendations
                    (ticker, scan_date, score, price_at_rec, rsi, sector,
                     verified, outcome, change_pct_1d)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                ("TEST", "2026-09-01", 75, 100, 50, "Technology", "good_mild", 2.5),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.db.get_confidence_for_ticker("TEST", "Technology", 50)
        self.assertTrue(result["available"])
        self.assertGreater(result["confidence"], 50)
        self.assertGreaterEqual(result["sample_size"], 1)


class MlFallbackTests(unittest.TestCase):
    def test_missing_model_never_impersonates_ml_probability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            predictor = StockMLPredictor(
                db_path=str(Path(temp_dir) / "missing.db"),
                model_path=str(Path(temp_dir) / "missing.joblib"),
            )
            result = predictor.predict_score({"score": 80})
            self.assertEqual(result["source"], "heuristic_fallback")
            self.assertIsNone(result["ml_score"])
            self.assertIsNone(result["probability"])
            self.assertEqual(result["confidence_level"], "NO DISPONIBLE")

            status = predictor.get_status()
            self.assertNotIn("db_path", status)
            self.assertNotIn("model_path", status)
            self.assertEqual(status["model_artifact"], "missing.joblib")


class UiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javascript = (VISOR / "app.js").read_text(encoding="utf-8")
        cls.html = (VISOR / "index.html").read_text(encoding="utf-8")

    def test_removed_dead_price_history_contract(self):
        self.assertNotIn("/prices/history", self.javascript)
        self.assertNotIn("loadPricesHistory", self.javascript)

    def test_only_real_tabs_are_bound(self):
        self.assertIn('.tab-btn[data-tab]', self.javascript)
        self.assertIn('function activateTab(tabId, button)', self.javascript)
        self.assertIn('id="btn-portfolio-shortcut"', self.html)
        self.assertNotIn('tab-btn portfolio-shortcut-btn', self.html)

    def test_accessible_tab_and_confirmation_contract(self):
        self.assertIn('role="tablist"', self.html)
        self.assertEqual(self.html.count('role="tab"'), 3)
        self.assertEqual(self.html.count('role="tabpanel"'), 3)
        self.assertIn('id="app-confirm-dialog"', self.html)
        self.assertIn('id="toast-region"', self.html)
        self.assertNotIn("confirm(`", self.javascript)
        self.assertNotIn("alert(`", self.javascript)


if __name__ == "__main__":
    unittest.main(verbosity=2)
