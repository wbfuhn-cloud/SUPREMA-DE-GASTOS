"""Pruebas de aceptación de la Fase 3: indicadores y heurística 3.0."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from technical_engine import (  # noqa: E402
    HEURISTIC_VERSION,
    atr_series,
    bollinger_frame,
    evaluate_heuristic,
    macd_frame,
    rsi_series,
    score_horizon,
)
from stock_scanner import process_single_ticker  # noqa: E402


def history(close, volume=1_000_000):
    values = np.asarray(close, dtype=float)
    spread = np.maximum(np.abs(values) * 0.01, 0.10)
    return pd.DataFrame(
        {
            "Open": values,
            "High": values + spread,
            "Low": values - spread,
            "Close": values,
            "Volume": np.full(len(values), volume),
        },
        index=pd.date_range("2025-01-01", periods=len(values), freq="D", tz="UTC"),
    )


VALID_QUOTE = {"is_stale": False, "quality_score": 1.0, "corporate_action_count": 0}


class FormulaParityTests(unittest.TestCase):
    def setUp(self):
        self.frame = history(100 + np.random.default_rng(42).normal(0, 1, 252).cumsum())
        self.close = self.frame["Close"]

    def assert_parity(self, actual, expected):
        mask = actual.notna() & expected.notna()
        relative = ((actual[mask] - expected[mask]).abs() / expected[mask].abs().clip(lower=1e-12))
        self.assertGreaterEqual(float((relative <= 0.001).mean()), 0.999)

    def test_rsi_matches_wilder_reference(self):
        delta = self.close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        expected = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
        self.assert_parity(rsi_series(self.close), expected)

    def test_macd_matches_ema_reference(self):
        expected_macd = self.close.ewm(span=12, adjust=False, min_periods=12).mean() - self.close.ewm(span=26, adjust=False, min_periods=26).mean()
        expected_signal = expected_macd.ewm(span=9, adjust=False, min_periods=9).mean()
        actual = macd_frame(self.close)
        self.assert_parity(actual["macd"], expected_macd)
        self.assert_parity(actual["signal"], expected_signal)
        self.assert_parity(actual["histogram"], expected_macd - expected_signal)

    def test_bollinger_matches_population_std_reference(self):
        middle = self.close.rolling(20, min_periods=20).mean()
        std = self.close.rolling(20, min_periods=20).std(ddof=0)
        actual = bollinger_frame(self.close)
        self.assert_parity(actual["middle"], middle)
        self.assert_parity(actual["upper"], middle + 2 * std)
        self.assert_parity(actual["lower"], middle - 2 * std)

    def test_atr_matches_wilder_reference(self):
        prior = self.close.shift()
        tr = pd.concat([
            self.frame["High"] - self.frame["Low"],
            (self.frame["High"] - prior).abs(),
            (self.frame["Low"] - prior).abs(),
        ], axis=1).max(axis=1)
        expected = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        self.assert_parity(atr_series(self.frame), expected)


class SyntheticRegimeTests(unittest.TestCase):
    def test_all_required_scenarios_have_expected_regime(self):
        rng = np.random.default_rng(7)
        scenarios = {
            "uptrend": np.linspace(50, 150, 252),
            "downtrend": np.linspace(150, 50, 252),
            "lateral": 100 + np.sin(np.linspace(0, 20 * np.pi, 252)) * 2,
            "jump": np.r_[np.full(251, 100.0), 120.0],
            "high_volatility": 100 + np.sin(np.linspace(0, 30 * np.pi, 252)) * 25,
            "noise": 100 + rng.normal(0, 1.5, 252),
        }
        for expected, prices in scenarios.items():
            with self.subTest(expected=expected):
                result = evaluate_heuristic(history(prices), quote=VALID_QUOTE)
                self.assertEqual(result["regime"], expected)

    def test_uptrend_and_downtrend_have_expected_long_horizon_states(self):
        up = evaluate_heuristic(history(np.linspace(50, 150, 252)), quote=VALID_QUOTE)
        down = evaluate_heuristic(history(np.linspace(150, 50, 252)), quote=VALID_QUOTE)
        self.assertEqual(up["horizons"]["trend"]["state"], "COMPRAR")
        self.assertEqual(down["horizons"]["trend"]["state"], "SALIR")


class HeuristicContractTests(unittest.TestCase):
    def test_four_action_states_and_abstention_are_explicit(self):
        base = {"rsi": None, "macd": None, "sma50": None, "trend60": None, "bollinger": None, "volume": None, "atr": None}
        expected = [(1.0, "COMPRAR"), (0.0, "MANTENER/ESPERAR"), (-0.3, "REDUCIR"), (-1.0, "SALIR")]
        for value, state in expected:
            signals = {**base, "rsi": value, "macd": value, "sma50": value, "trend60": value, "bollinger": value, "volume": value, "atr": value}
            self.assertEqual(score_horizon(signals, "swing")["state"], state)
        self.assertEqual(score_horizon(base, "swing")["state"], "SIN SEÑAL")

    def test_missing_inputs_abstain_instead_of_becoming_zero(self):
        result = evaluate_heuristic(history(np.linspace(100, 102, 10)), quote=VALID_QUOTE)
        self.assertEqual(result["state"], "SIN SEÑAL")
        self.assertLess(result["coverage"], 0.60)
        self.assertTrue(result["missing"])

    def test_contributions_reconcile_to_displayed_score(self):
        result = evaluate_heuristic(history(np.linspace(50, 150, 252)), quote=VALID_QUOTE)
        self.assertAlmostEqual(sum(result["contributions"].values()), result["score"], delta=0.01)

    def test_every_evaluation_is_versioned(self):
        result = evaluate_heuristic(history(np.linspace(50, 150, 252)), quote=VALID_QUOTE)
        self.assertEqual(result["heuristic_version"], HEURISTIC_VERSION)

    def test_leveraged_etf_never_gets_long_term_classic_buy(self):
        result = evaluate_heuristic(
            history(np.linspace(50, 150, 252)), quote=VALID_QUOTE, is_leveraged=True
        )
        self.assertEqual(result["horizons"]["trend"]["state"], "SIN SEÑAL")
        self.assertTrue(any("apalancado" in item for item in result["restrictions"]))

    def test_stale_quote_forces_abstention(self):
        result = evaluate_heuristic(
            history(np.linspace(50, 150, 252)),
            quote={"is_stale": True, "quality_score": 1.0},
        )
        self.assertEqual(result["state"], "SIN SEÑAL")

    def test_illiquid_asset_forces_abstention(self):
        result = evaluate_heuristic(
            history(np.linspace(50, 150, 252), volume=50_000), quote=VALID_QUOTE
        )
        self.assertEqual(result["state"], "SIN SEÑAL")
        self.assertTrue(any("liquidez" in item for item in result["restrictions"]))

    def test_corporate_action_is_disclosed(self):
        quote = {**VALID_QUOTE, "corporate_action_count": 1}
        result = evaluate_heuristic(history(np.linspace(50, 150, 252)), quote=quote)
        self.assertTrue(any("acción corporativa" in item for item in result["restrictions"]))

    def test_scanner_and_portfolio_emit_rule_version(self):
        scanner = (VISOR / "stock_scanner.py").read_text(encoding="utf-8")
        portfolio = (VISOR / "portfolio_analyzer.py").read_text(encoding="utf-8")
        self.assertIn("'Heuristic_Version': HEURISTIC_VERSION", scanner)
        self.assertIn('"heuristic_version": HEURISTIC_VERSION', portfolio)

    def test_runtime_scanner_recommendation_contains_version_and_explanation(self):
        frame = history(np.linspace(50, 150, 252))
        quote = {
            "symbol": "TEST",
            "price": 150.0,
            "is_stale": False,
            "quality_score": 1.0,
            "quality_issues": [],
            "corporate_action_count": 0,
        }
        with (
            patch("stock_scanner.quote_from_history", return_value=quote),
            patch("stock_scanner.is_cache_valid", return_value=False),
            patch("stock_scanner._fetch_quote_batch", return_value={"TEST": {"marketCap": 5e9, "beta": 1.1}}),
            patch("stock_scanner.save_to_cache"),
            patch("ml_predictor.get_ml_predictor") as predictor_factory,
        ):
            predictor_factory.return_value.predict_score.return_value = {
                "ml_score": None,
                "confidence_level": "NO DISPONIBLE",
                "feature_breakdown": {},
                "source": "fallback",
            }
            result = process_single_ticker("TEST", use_cache=False, prefetched_history=frame)
        self.assertEqual(result["Heuristic_Version"], HEURISTIC_VERSION)
        self.assertIn(result["Signal_State"], {"COMPRAR", "ESPERAR", "MANTENER", "REDUCIR", "SALIR", "SIN SEÑAL"})
        self.assertAlmostEqual(sum(result["Score_Contributions"].values()), result["Score"], delta=0.01)

    def test_alerts_consume_state_without_mutating_it_with_confidence(self):
        server = (ROOT / "src" / "server.py").read_text(encoding="utf-8")
        self.assertIn("signal_state == 'COMPRAR'", server)
        self.assertIn("signal_state in {'REDUCIR', 'SALIR'}", server)
        self.assertNotIn("score >= 75 and ai_confidence", server)

    def test_ui_exposes_version_contributions_horizons_and_missing_data(self):
        app = (VISOR / "app.js").read_text(encoding="utf-8")
        for field in ("Heuristic_Version", "Horizon_Scores", "Score_Contributions", "Missing_Indicators"):
            self.assertIn(field, app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
