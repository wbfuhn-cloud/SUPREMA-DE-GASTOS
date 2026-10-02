import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from production_controls import (KillSwitch, OperationalMetrics, RateLimiter,
                                 authorized_write, correlation_id, promotion_record)  # noqa: E402


class Phase11IntegrationTests(unittest.TestCase):
    def test_auth_rate_limit_and_correlation_are_fail_closed_in_production(self):
        self.assertFalse(authorized_write(None, None, "production"))
        self.assertTrue(authorized_write("secret", "Bearer secret", "production"))
        self.assertFalse(authorized_write("secret", "Bearer wrong", "production"))
        limiter = RateLimiter(limit=2, window_seconds=10)
        self.assertEqual([limiter.allow("client", now=value) for value in (0, 1, 2)], [True, True, False])
        self.assertEqual(correlation_id("trace-123"), "trace-123")
        self.assertNotEqual(correlation_id("ruta C:\\Users\\privada"), "ruta C:\\Users\\privada")

    def test_kill_switch_forces_abstention_without_stopping_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            switch = KillSwitch(Path(temp) / "kill-switch.json")
            original = {"state": "COMPRAR", "symbol": "AAA", "observed": True}
            self.assertEqual(switch.enforce(original), original)
            switch.set(True, "DATA_CORRUPTION", "operator@example")
            blocked = switch.enforce(original)
            self.assertEqual(blocked["state"], "SIN SEÑAL")
            self.assertTrue(blocked["observed"])
            self.assertEqual(blocked["kill_switch_reason"], "DATA_CORRUPTION")

    def test_observability_and_human_promotion_audit_are_complete(self):
        metrics = OperationalMetrics()
        for latency, status in ((100, 200), (300, 200), (700, 503)):
            metrics.observe("/api/test", latency, status)
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["errors"]["/api/test"], 1)
        self.assertEqual(snapshot["latency_p95_ms"]["/api/test"], 300)
        record = promotion_record("model-sha", {"paper": "approved"}, "risk-owner", "APPROVE")
        self.assertEqual(record["approver"], "risk-owner")
        with self.assertRaises(ValueError):
            promotion_record("model-sha", {}, "", "APPROVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
