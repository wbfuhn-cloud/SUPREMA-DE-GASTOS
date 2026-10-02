import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from explainability import adaptive_ai_status, filter_history, signal_explanation  # noqa: E402


class Phase10IntegrationTests(unittest.TestCase):
    def test_signal_contract_exposes_risk_versions_modules_and_missing_values(self):
        view = signal_explanation({
            "Signal_State": "ESPERAR", "Price": 100, "Score": .4, "Data_Quality": .99,
            "Quote": {"provider": "test", "market_timestamp": "2026-01-05T15:00:00Z", "freshness_seconds": 30},
            "Heuristic_Version": "2.0", "Fusion_Version": "1.0", "Model_Version": "unavailable",
            "ML_Degraded_Reason": "modelo no aprobado", "Calibrated_Probability": None,
            "Fusion_Explanation": {"factors_for": ["tendencia"], "factors_against": ["sin ML"]},
        })
        self.assertEqual(view["calibrated_ml_probability"], "N/D")
        self.assertEqual(view["uncertainty"], "no cuantificada")
        self.assertFalse(view["modules"]["ml"]["active"])
        self.assertFalse(view["modules"]["fourier"]["active"])
        self.assertIn("no garantiza resultados", view["disclaimer"])
        self.assertIn("probabilidad_ml", view["missing_data"])

    def test_adaptive_panel_uses_only_oos_evidence_and_explains_degradation(self):
        status = adaptive_ai_status(
            ml_status={"production_approved": False, "model_version": "legacy", "metrics": {},
                       "degraded_reason": "legacy_model_not_reproducible_or_unvalidated"},
            learner_stats={"verified": 0}, paper_status={"approved": False},
        )
        self.assertEqual(status["out_of_sample_metrics"], "N/D")
        self.assertEqual(status["modules"]["ml"], "experimental_inactivo")
        self.assertEqual(status["operational_state"], "paper_trading")
        self.assertNotIn("training", str(status["out_of_sample_metrics"]).lower())

    def test_history_filters_cover_date_ticker_model_signal_horizon_and_result(self):
        rows = [{"scan_date": "2026-01-05T15:00:00Z", "ticker": "AAA", "model_version": "m1",
                 "signal": "COMPRAR", "horizon": "5-20", "outcome": "COMPRA_EXITOSA"},
                {"scan_date": "2026-02-01T15:00:00Z", "ticker": "BBB", "model_version": "m2",
                 "signal": "SALIR", "horizon": "1-3", "outcome": "SALIDA_INCORRECTA"}]
        selected = filter_history(rows, date_from="2026-01-01", date_to="2026-01-31", ticker="AAA",
                                  model="m1", signal="COMPRAR", horizon="5-20", result="COMPRA_EXITOSA")
        self.assertEqual(selected, [rows[0]])
        self.assertEqual(filter_history(rows, ticker="ZZZ"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
