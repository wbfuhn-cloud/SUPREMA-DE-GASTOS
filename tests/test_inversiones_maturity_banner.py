import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from maturity_status import build_maturity_status  # noqa: E402


def gate(approved=False):
    checks = {"sample": approved, "availability": approved}
    return {"approved": approved, "checks": checks,
            "decision": "APPROVED" if approved else "EXTEND_PAPER_TRADING"}


class MaturityBannerTests(unittest.TestCase):
    def test_empty_evidence_stays_experimental_and_requests_scan(self):
        status = build_maturity_status(
            paper_metrics={}, paper_gate=gate(),
            release_gate={"approved_for_production": False, "decision": "RESEARCH_AND_PAPER_ONLY"},
            scan_results=[],
        )
        self.assertEqual(status["current_phase"]["number"], 9)
        self.assertEqual(status["solidity"]["level"], "EXPERIMENTAL")
        self.assertEqual(status["next_step"]["code"], "RUN_SCAN")
        self.assertFalse(status["solidity"]["real_money_enabled"])

    def test_gates_advance_only_after_quality_and_required_evidence(self):
        metrics = {"market_sessions": 60, "eligible_signals": 300,
                   "positive_executable_signals": 75}
        low = build_maturity_status(
            paper_metrics=metrics, paper_gate=gate(),
            release_gate={"approved_for_production": False},
            scan_results=[{"Data_Quality": .91}],
        )
        self.assertEqual(low["next_step"]["code"], "DATA_QUALITY")

        approved = build_maturity_status(
            paper_metrics=metrics, paper_gate=gate(True),
            release_gate={"approved_for_production": True, "real_money_enabled": True,
                          "decision": "PRODUCTION_APPROVED"},
            scan_results=[{"Data_Quality": .99}],
        )
        self.assertEqual(approved["current_phase"]["number"], 12)
        self.assertEqual(approved["solidity"]["level"], "SOLIDO")
        self.assertTrue(approved["solidity"]["real_money_enabled"])

    def test_ui_wires_dynamic_banner_and_preserves_portfolio_during_read_only_refresh(self):
        html = (VISOR / "index.html").read_text(encoding="utf-8")
        js = (VISOR / "app.js").read_text(encoding="utf-8")
        server = (ROOT / "src" / "server.py").read_text(encoding="utf-8")
        self.assertIn('id="maturity-banner"', html)
        self.assertIn('id="ai-worker-banner"', html)
        self.assertIn("loadMaturityStatus()", js)
        self.assertIn("startAdaptiveWorkerHeartbeat()", js)
        self.assertIn("DETENIDO O SIN CONEXIÓN", js)
        self.assertIn("Mantén abierto el servidor Python", js)
        self.assertIn("renderPortfolioSnapshot(data.portfolio || {})", js)
        self.assertIn("fetch(`${API_URL}/portfolio/analyze`)", js)
        self.assertIn("methods=['GET', 'POST']", server)


if __name__ == "__main__":
    unittest.main(verbosity=2)
