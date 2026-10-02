"""Pruebas de aceptación para etiquetas y ciclo de aprendizaje de la Fase 4."""

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from prediction_ledger import CostPolicy, NyseCalendar, PredictionLedger  # noqa: E402


def payload(horizon=3, prediction_id=None, signal="COMPRAR"):
    return {
        "prediction_id": prediction_id,
        "symbol": "TEST",
        "market": "XNYS",
        "data_timestamp": "2026-09-08T20:00:00Z",
        "emitted_at": "2026-09-08T20:01:00Z",
        "horizon_sessions": horizon,
        "expected_entry_price": 100.0,
        "features": {"atr": 2.0, "rsi": 50.0},
        "feature_version": "3.0.0",
        "signal": signal,
        "probability": None,
        "score": 70.0,
        "model_name": "heuristic",
        "model_version": "3.0.0",
        "model_hash": "a" * 64,
        "risk_rules": {"max_risk_pct": 2.0},
        "data_provider": "test_provider",
        "quote": {"symbol": "TEST", "price": 100.0, "provider": "test_provider"},
    }


def market_history(sessions, opens, closes):
    index = [pd.Timestamp(f"{day.isoformat()}T20:00:00Z") for day in sessions]
    return pd.DataFrame(
        {
            "Open": opens,
            "High": np.maximum(opens, closes) + 1,
            "Low": np.minimum(opens, closes) - 1,
            "Close": closes,
            "Volume": np.full(len(sessions), 1_000_000),
        },
        index=index,
    )


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "ledger.db"
        self.ledger = PredictionLedger(self.db_path)

    def tearDown(self):
        self.temp.cleanup()


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.calendar = NyseCalendar()

    def test_weekend_and_observed_independence_day(self):
        self.assertEqual(self.calendar.next_session(date(2026, 7, 2)), date(2026, 7, 6))

    def test_good_friday_is_not_a_session(self):
        self.assertFalse(self.calendar.is_session(date(2026, 4, 3)))
        self.assertEqual(self.calendar.next_session(date(2026, 4, 2)), date(2026, 4, 6))

    def test_thanksgiving_and_half_session(self):
        self.assertFalse(self.calendar.is_session(date(2026, 11, 26)))
        self.assertTrue(self.calendar.is_half_session(date(2026, 11, 27)))
        self.assertEqual(self.calendar.close_time(date(2026, 11, 27)).hour, 18)

    def test_next_year_observed_new_year_is_closed(self):
        self.assertFalse(self.calendar.is_session(date(2021, 12, 31)))


class ImmutablePredictionTests(LedgerCase):
    def test_prediction_contains_all_trace_fields_and_cannot_change(self):
        prediction_id = self.ledger.record_prediction(payload())
        row = self.ledger.get_prediction(prediction_id)
        required = {
            "prediction_id", "symbol", "market", "data_timestamp", "emitted_at",
            "horizon_sessions", "expected_entry_session", "expected_entry_price",
            "features_json", "feature_version", "signal", "probability", "score",
            "model_name", "model_version", "model_hash", "risk_rules_json",
            "data_provider", "quote_json",
        }
        self.assertTrue(required.issubset(row))
        with self.ledger._connection() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE predictions_v3 SET score=1 WHERE prediction_id=?", (prediction_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM predictions_v3 WHERE prediction_id=?", (prediction_id,))

    def test_each_horizon_is_a_distinct_prediction_and_result(self):
        ids = [self.ledger.record_prediction(payload(horizon=h)) for h in (1, 3, 5, 10, 20)]
        with self.ledger._connection() as connection:
            rows = connection.execute(
                "SELECT p.horizon_sessions,r.horizon_sessions FROM predictions_v3 p JOIN prediction_results_v3 r USING(prediction_id)"
            ).fetchall()
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(sorted((row[0], row[1]) for row in rows), [(1, 1), (3, 3), (5, 5), (10, 10), (20, 20)])

    def test_scan_integration_emits_ids_for_all_horizons_and_sanitizes_nan(self):
        row = {
            "Ticker": "TEST", "Score": 70.0, "Signal_Eligible": True,
            "Signal_State": "COMPRAR", "Heuristic_Version": "3.0.0",
            "ML_Source": "fallback", "Market_Cap": float("nan"), "ATR": 2.0,
            "Quote": {
                "symbol": "TEST", "price": 100.0, "provider": "test_provider",
                "market_timestamp": "2026-09-08T20:00:00Z",
                "received_at": "2026-09-08T20:01:00Z",
            },
            "Horizon_Scores": {
                "short": {"state": "COMPRAR", "score": 71.0},
                "swing": {"state": "MANTENER/ESPERAR", "score": 55.0},
                "trend": {"state": "REDUCIR", "score": 40.0},
            },
        }
        ids = self.ledger.record_scan_results([row])
        self.assertEqual(len(ids), 5)
        self.assertEqual(set(row["Prediction_IDs"]), {"1", "3", "5", "10", "20"})
        with self.ledger._connection() as connection:
            features = [json.loads(item[0]) for item in connection.execute("SELECT features_json FROM predictions_v3")]
        self.assertTrue(all(item["market_cap"] is None for item in features))


class OutcomeTests(LedgerCase):
    def test_all_five_horizons_use_their_own_due_session(self):
        sessions = [date(2026, 9, day) for day in (9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 28, 29, 30)]
        sessions += [date(2026, 10, day) for day in (1, 2, 5, 6)]
        history = market_history(sessions, list(range(100, 120)), list(range(101, 121)))
        expected_due = {1: sessions[0], 3: sessions[2], 5: sessions[4], 10: sessions[9], 20: sessions[19]}
        for horizon, due in expected_due.items():
            with self.subTest(horizon=horizon):
                prediction_id = self.ledger.record_prediction(payload(horizon=horizon))
                result = self.ledger.verify(
                    prediction_id, history, CostPolicy(),
                    self.ledger.calendar.close_time(due) + pd.Timedelta(minutes=1),
                )
                self.assertEqual(result["horizon_sessions"], horizon)
                self.assertEqual(result["exit_session"], due.isoformat())
    def test_uses_next_session_open_exit_close_and_all_configured_costs(self):
        prediction_id = self.ledger.record_prediction(payload(horizon=3))
        sessions = [date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11)]
        history = market_history(sessions, [101, 102, 103], [102, 104, 106])
        costs = CostPolicy(commission_entry_bps=2, commission_exit_bps=3, spread_bps=4, slippage_bps=5)
        result = self.ledger.verify(
            prediction_id, history, costs, datetime(2026, 9, 11, 21, tzinfo=timezone.utc)
        )
        self.assertEqual(result["entry_session"], "2026-09-09")
        self.assertEqual(result["exit_session"], "2026-09-11")
        self.assertEqual(result["entry_price"], 101)
        self.assertEqual(result["exit_price"], 106)
        self.assertAlmostEqual(result["gross_return"], 106 / 101 - 1)
        self.assertAlmostEqual(result["total_cost"], 0.0014)
        self.assertAlmostEqual(result["net_return"], 106 / 101 - 1 - 0.0014)
        for field in ("commission_entry", "commission_exit", "spread_cost", "slippage_cost"):
            self.assertIsNotNone(result[field])
        self.assertEqual(result["market_label"], "COMPRA_EXITOSA")

    def test_exit_signal_measures_opportunity_cost(self):
        prediction_id = self.ledger.record_prediction(payload(horizon=1, signal="SALIR"))
        history = market_history([date(2026, 9, 9)], [100], [90])
        result = self.ledger.verify(
            prediction_id, history, CostPolicy(), datetime(2026, 9, 9, 21, tzinfo=timezone.utc)
        )
        self.assertEqual(result["market_label"], "SALIDA_CORRECTA")
        self.assertEqual(result["opportunity_cost"], result["net_return"])

    def test_automatic_verification_completes_at_least_99_percent_by_due_session(self):
        ids = [self.ledger.record_prediction(payload(horizon=1)) for _ in range(100)]
        history = market_history([date(2026, 9, 9)], [100], [102])
        summary = self.ledger.verify_due(
            lambda _symbol, _entry, _due: history,
            as_of=datetime(2026, 9, 9, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(summary["verified"], len(ids))
        self.assertGreaterEqual(summary["verified"] / len(ids), 0.99)
        self.assertEqual(self.ledger.unresolved_count(), 0)

    def test_missing_market_data_becomes_explained_irrecoverable_after_grace(self):
        self.ledger.record_prediction(payload(horizon=1))
        summary = self.ledger.verify_due(
            lambda *_: None,
            as_of=datetime(2026, 9, 11, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(summary["irrecoverable"], 1)
        with self.ledger._connection() as connection:
            row = connection.execute("SELECT * FROM prediction_results_v3").fetchone()
        self.assertEqual(row["status"], "IRRECOVERABLE")
        self.assertIn("suspension/delisting", row["resolution_reason"])


class FeedbackTests(LedgerCase):
    def test_feedback_is_append_only_structured_and_does_not_change_prediction(self):
        prediction_id = self.ledger.record_prediction(payload())
        before = self.ledger.get_prediction(prediction_id)
        first = self.ledger.record_feedback(
            prediction_id, "positive", "explanation", "user-1", "owner", "clara"
        )
        second = self.ledger.record_feedback(
            prediction_id, "negative", "timing", "user-1", "owner", "tarde"
        )
        after = self.ledger.get_prediction(prediction_id)
        self.assertNotEqual(first, second)
        self.assertEqual(before, after)
        with self.ledger._connection() as connection:
            feedback = connection.execute("SELECT * FROM prediction_feedback_v3 ORDER BY submitted_at").fetchall()
            adjustments = connection.execute("SELECT COUNT(*) FROM model_adjustment_audit_v3").fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE prediction_feedback_v3 SET reason='other' WHERE feedback_id=?", (first,))
        self.assertEqual(len(feedback), 2)
        self.assertTrue(all(row["user_id"] and row["user_role"] and row["reason"] and row["symbol"] for row in feedback))
        self.assertEqual(adjustments, 0)

    def test_adjustment_proposal_and_review_have_audit_trail_without_activation(self):
        adjustment_id = self.ledger.propose_adjustment(
            "trainer-1", {"sample_size": 500}, "3.0.0", "3.0.1-candidate", "batch review"
        )
        self.ledger.review_adjustment(adjustment_id, True, "reviewer-1", "evidence accepted")
        with self.ledger._connection() as connection:
            row = connection.execute(
                "SELECT * FROM model_adjustment_audit_v3 WHERE adjustment_id=?", (adjustment_id,)
            ).fetchone()
        self.assertEqual(row["status"], "APPROVED")
        self.assertEqual(row["reviewed_by"], "reviewer-1")
        self.assertNotEqual(row["status"], "APPLIED")


class LegacyRecoveryTests(LedgerCase):
    def test_all_ten_legacy_rows_receive_explicit_resolution(self):
        legacy_path = Path(self.temp.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.execute("CREATE TABLE recommendations(id INTEGER,ticker TEXT,scan_date TEXT,created_at TEXT,verified INTEGER)")
        connection.executemany(
            "INSERT INTO recommendations VALUES (?,?,?,?,0)",
            [(index, f"T{index}", "2026-09-08", "2026-09-08 15:09:14") for index in range(1, 11)],
        )
        connection.commit()
        connection.close()
        rows = self.ledger.import_legacy_as_irrecoverable(legacy_path)
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["status"] == "IRRECOVERABLE" and row["reason"] for row in rows))
        with self.ledger._connection() as destination:
            unresolved = destination.execute(
                "SELECT COUNT(*) FROM legacy_recovery_v3 WHERE status!='IRRECOVERABLE' OR reason=''"
            ).fetchone()[0]
        self.assertEqual(unresolved, 0)


class IntegrationContractTests(unittest.TestCase):
    def test_feedback_endpoint_requires_identity_reason_and_prediction(self):
        server = (ROOT / "src" / "server.py").read_text(encoding="utf-8")
        for field in ("prediction_id", "feedback", "reason", "user_id", "user_role"):
            self.assertIn(field, server)

    def test_legacy_immediate_weight_mutation_is_not_called_by_new_feedback(self):
        source = (VISOR / "recommendation_learner.py").read_text(encoding="utf-8")
        method = source.split("def submit_user_feedback", 1)[1].split("def record_live_alert", 1)[0]
        self.assertNotIn("adjust_weight", method)
        self.assertNotIn("PENALTY_FACTOR", method)

    def test_independent_recovery_job_is_started(self):
        server = (ROOT / "src" / "server.py").read_text(encoding="utf-8")
        self.assertIn("def run_prediction_recovery_loop", server)
        self.assertIn('name="PredictionRecovery-Bolsa"', server)

    def test_ui_explains_feedback_does_not_mutate_the_model(self):
        html = (VISOR / "index.html").read_text(encoding="utf-8")
        self.assertIn("Ningún comentario modifica el modelo", html)
        self.assertIn("revisión y aprobación explícitas", html)
        self.assertNotIn("Promedio a 1 día", html)
        self.assertNotIn("Resultado (1d)", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
