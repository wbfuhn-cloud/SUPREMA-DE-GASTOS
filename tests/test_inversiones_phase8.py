import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from backtesting import (  # noqa: E402
    CostModel, EventDrivenBacktester, MarketBar, SignalEvent,
    bootstrap_expected_value, phase8_approval, walk_forward_splits,
)


class Phase8IntegrationTests(unittest.TestCase):
    def test_event_execution_uses_next_open_and_models_friction_actions_and_rejections(self):
        start = date(2026, 1, 5)
        sessions = [start + timedelta(days=index) for index in range(5)]
        bars = []
        opens = [100, 110, 56, 58, 60]
        for index, session in enumerate(sessions):
            bars.append(MarketBar(session, "AAA", opens[index], opens[index] + 2,
                                  opens[index] - 2, opens[index] + 1, 100_000, True,
                                  split_factor=2.0 if index == 2 else 1.0,
                                  dividend=0.50 if index == 2 else 0.0))
        bars.extend([
            MarketBar(sessions[1], "BBB", 10, 11, 9, 10, 100_000, False),
            MarketBar(sessions[1], "CCC", 10, 11, 9, 10, 100, True),
        ])
        signals = [
            SignalEvent(sessions[0], "AAA", "COMPRAR", "5-20", shares=10),
            SignalEvent(sessions[0], "BBB", "COMPRAR", "5-20", shares=10),
            SignalEvent(sessions[0], "CCC", "COMPRAR", "5-20", shares=10),
            SignalEvent(sessions[3], "AAA", "SALIR", "5-20"),
        ]
        result = EventDrivenBacktester(costs=CostModel(max_volume_participation=.01)).run(bars, signals)
        self.assertEqual(result["fills"][0]["emitted_session"], sessions[0].isoformat())
        self.assertEqual(result["fills"][0]["session"], sessions[1].isoformat())
        self.assertEqual(result["fills"][0]["raw_open"], 110)
        self.assertEqual(result["trades"][0]["shares"], 20)
        self.assertGreater(result["metrics"]["total_cost"], 0)
        reasons = {item["reason"] for item in result["rejected_orders"]}
        self.assertIn("NOT_HISTORICAL_UNIVERSE_MEMBER", reasons)
        self.assertIn("ORDER_NOT_FILLED_LIQUIDITY", reasons)

    def test_walk_forward_reserves_final_test_and_bootstrap_is_reproducible(self):
        anchored = walk_forward_splits(500, 200, 50, anchored=True, final_holdout=100)
        rolling = walk_forward_splits(500, 200, 50, anchored=False, final_holdout=100)
        self.assertTrue(anchored and rolling)
        self.assertTrue(all(fold["test"].max() < 400 for fold in anchored + rolling))
        self.assertTrue(all(not set(fold["train"]).intersection(fold["test"]) for fold in anchored + rolling))
        first = bootstrap_expected_value([10, 5, -2, 7, 3], samples=1000, seed=8)
        self.assertEqual(first, bootstrap_expected_value([10, 5, -2, 7, 3], samples=1000, seed=8))

    def test_phase_gate_rejects_missing_real_evidence_and_exposes_all_metrics(self):
        bars = [MarketBar(date(2026, 1, 5) + timedelta(days=i), "AAA", 100+i, 102+i,
                          99+i, 101+i, 100_000, True) for i in range(4)]
        result = EventDrivenBacktester().run(bars, [])
        required = {"cagr", "total_return", "annualized_volatility", "sharpe", "sortino",
                    "maximum_drawdown", "drawdown_duration_sessions", "calmar", "profit_factor",
                    "win_rate", "average_payoff", "expected_value_per_trade", "turnover", "exposure",
                    "average_holding_days", "buy_precision", "exit_precision", "total_cost",
                    "approximate_capacity"}
        self.assertTrue(required.issubset(result["metrics"]))
        gate = phase8_approval(result["metrics"], bootstrap_expected_value([]), benchmark_sharpe=0,
                               profitable_fold_ratio=0, double_costs_viable=False,
                               sensitivity_robust=False, fourier_ablation_passed=False,
                               historical_universe=False, final_test_untouched=True)
        self.assertFalse(gate["approved"])
        self.assertIn("historical_universe", gate["failed"])
        self.assertIn("fourier", gate["failed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
