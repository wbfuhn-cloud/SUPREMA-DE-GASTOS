import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from release_governance import (artifact_manifest, current_project_gate,
                                final_release_gate, rollback_decision)  # noqa: E402


class Phase12IntegrationTests(unittest.TestCase):
    def test_final_gate_fails_closed_when_any_phase_evidence_or_scan_is_missing(self):
        phases = {phase: True for phase in range(12)}
        phases[9] = False
        evidence = {name: True for name in ("data_report", "validation_report", "active_comparison",
                                             "human_review", "rollback_plan", "review_expiry", "artifact_hash")}
        gate = final_release_gate(phases, evidence, critical_high_vulnerabilities=None,
                                  real_money_requested=True)
        self.assertFalse(gate["approved_for_production"])
        self.assertFalse(gate["real_money_enabled"])
        self.assertIn("phase_9", gate["failed"])
        self.assertIn("security_scan_clean", gate["failed"])

    def test_signed_manifest_is_deterministic_and_rollback_thresholds_are_automatic(self):
        files = [("b.txt", b"two"), ("a.txt", b"one")]
        self.assertEqual(artifact_manifest(files, "3.0"), artifact_manifest(reversed(files), "3.0"))
        decision = rollback_decision(
            {"error_rate": .06, "latency_p95_ms": 300, "stale_data_rate": 0},
            {"max_error_rate": .05, "max_latency_p95_ms": 500, "max_stale_data_rate": .01},
        )
        self.assertTrue(decision["rollback"])
        self.assertEqual(decision["reasons"], ["ERROR_RATE"])

    def test_current_project_remains_research_and_paper_only(self):
        gate = current_project_gate()
        self.assertEqual(gate["decision"], "RESEARCH_AND_PAPER_ONLY")
        self.assertFalse(gate["real_money_enabled"])
        self.assertFalse(gate["phase_checks"]["phase_5"])
        self.assertFalse(gate["phase_checks"]["phase_9"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
