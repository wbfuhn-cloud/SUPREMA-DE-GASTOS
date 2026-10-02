import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from paper_trading import (ExecutionObservation, PaperTradingLedger, freeze_protocol,
                           kill_switch_reason, phase9_approval)  # noqa: E402


class Phase9IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = PaperTradingLedger(Path(self.temp.name) / "paper.db")
        self.protocol = freeze_protocol({"model": "experiment_only", "rules": "1.0.0", "threshold": .65})

    def tearDown(self):
        self.temp.cleanup()

    def signal(self):
        return {"decision_hash": "abc123", "ticker": "AAA", "signal": "COMPRAR", "horizon": "5-20",
                "model_version": "unavailable", "rules_version": "1.0.0", "quoted_price": 100,
                "data_quality": .99, "market_session": "2026-01-05",
                "emitted_at_utc": "2026-01-05T15:00:00Z", "data_timestamp_utc": "2026-01-05T14:59:00Z",
                "baseline_signal": "ESPERAR", "candidate_signal": "COMPRAR"}

    def test_frozen_protocol_and_append_only_signal_ledger(self):
        self.assertEqual(self.protocol, freeze_protocol(self.protocol["configuration"]))
        self.assertTrue(self.ledger.append_signal(self.signal(), self.protocol["configuration_hash"]))
        self.assertFalse(self.ledger.append_signal(self.signal(), self.protocol["configuration_hash"]))
        metrics = self.ledger.metrics("2026-01-05T16:00:00Z")
        self.assertEqual(metrics["eligible_signals"], 1)
        self.assertEqual(metrics["duplicate_signals"], 0)
        self.assertEqual(metrics["stale_data_used"], 0)

    def test_execution_observation_incidents_and_kill_switch_are_auditable(self):
        self.ledger.append_signal(self.signal(), self.protocol["configuration_hash"])
        execution = self.ledger.record_execution(ExecutionObservation("abc123", 100.25, 8, 350, 5))
        self.assertAlmostEqual(execution["entry_deviation_bps"], 25.0)
        incident = self.ledger.open_incident("critical", "provider", "Proveedor sin respuesta")
        self.ledger.record_kill_switch_drill("provider_outage", True, "Bloqueó nuevas órdenes")
        self.assertEqual(kill_switch_reason(daily_loss_pct=0, max_daily_loss_pct=.02,
                                           data_corrupt=False, drift_detected=False,
                                           provider_available=False), "PROVIDER_OUTAGE")
        self.assertEqual(self.ledger.metrics()["open_critical_incidents"], 1)
        self.ledger.close_incident(incident)
        self.assertEqual(self.ledger.metrics()["kill_switch_success_rate"], 1.0)

    def test_gate_extends_until_real_prospective_sample_is_complete(self):
        gate = phase9_approval(self.ledger.metrics(), availability=None,
                               live_backtest_deviation=None, net_expected_value=None,
                               drawdown_within_limit=None)
        self.assertFalse(gate["approved"])
        self.assertEqual(gate["decision"], "EXTEND_PAPER_TRADING")
        self.assertIn("duration_60_sessions", gate["failed"])
        self.assertIn("sample_300_75", gate["failed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
