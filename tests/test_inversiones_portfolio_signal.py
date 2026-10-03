import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from portfolio_status import classify_portfolio_position  # noqa: E402


class PortfolioSignalTests(unittest.TestCase):
    def test_green_when_profit_is_supported_by_valid_hold_signal(self):
        result = classify_portfolio_position(
            pl_pct=8.5, signal_state="MANTENER", signal_eligible=True,
            data_quality=.99, quote_adjusted=True, weekly_change_pct=3.2,
            trend_state="COMPRAR", upside_scenario_3m_pct=40,
        )
        self.assertEqual((result["color"], result["label"]), ("green", "VA BIEN"))
        self.assertTrue(result["pnl_reliable"])
        self.assertIn("AGUANTA", result["summary"])
        self.assertIn("+40%", result["summary"])
        self.assertIn("Te avisaré", result["monitoring_note"])

    def test_red_when_loss_limit_or_valid_exit_is_triggered(self):
        loss = classify_portfolio_position(
            pl_pct=-12, signal_state="SIN SEÑAL", signal_eligible=False,
            data_quality=0, quote_adjusted=False,
        )
        exit_signal = classify_portfolio_position(
            pl_pct=4, signal_state="SALIR", signal_eligible=True,
            data_quality=.98, quote_adjusted=True,
        )
        self.assertEqual(loss["color"], "red")
        self.assertIn("validar precio", loss["confidence"])
        self.assertIn("antes de perder más", loss["summary"])
        self.assertEqual(exit_signal["label"], "VENTA / REDUCIR")

    def test_yellow_blocks_unverified_profit_and_leveraged_split_risk(self):
        stale = classify_portfolio_position(
            pl_pct=25, signal_state="MANTENER", signal_eligible=False,
            data_quality=0, quote_adjusted=False,
        )
        leveraged = classify_portfolio_position(
            pl_pct=380, signal_state="MANTENER", signal_eligible=True,
            data_quality=.99, is_leveraged=True, quote_adjusted=False,
        )
        recovery = classify_portfolio_position(
            pl_pct=-4, signal_state="MANTENER", signal_eligible=True,
            data_quality=.99, quote_adjusted=True, trend_state="MANTENER",
        )
        self.assertEqual(stale["label"], "ESPERAR / VALIDAR")
        self.assertIn("no es responsable prometer", stale["summary"])
        self.assertEqual(leveraged["color"], "yellow")
        self.assertIn("ajuste corporativo", leveraged["reason"])
        self.assertIn("4–5 meses", recovery["summary"])
        self.assertIn("-10%", recovery["monitoring_note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
