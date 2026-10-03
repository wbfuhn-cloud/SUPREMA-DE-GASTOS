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
            data_quality=.99, quote_adjusted=True,
        )
        self.assertEqual((result["color"], result["label"]), ("green", "VA BIEN"))
        self.assertTrue(result["pnl_reliable"])

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
        self.assertEqual(stale["label"], "ESPERAR / VALIDAR")
        self.assertEqual(leveraged["color"], "yellow")
        self.assertIn("ajuste corporativo", leveraged["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
