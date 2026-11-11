"""Pruebas de contrato, calidad, frescura y consistencia de la Fase 2."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from market_data import (  # noqa: E402
    apply_adjusted_close,
    ensure_quote_contract,
    exchange_rate_contract,
    quote_from_history,
    reconcile_quotes,
    validate_ohlcv,
)
from portfolio_analyzer import analyze_ticker_strategy  # noqa: E402


def history(rows=252, end="2026-10-01T20:00:00Z"):
    index = pd.date_range(end=end, periods=rows, freq="D", tz="UTC")
    close = np.linspace(90.0, 110.0, rows)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(rows, 1_000_000),
        },
        index=index,
    )


class MarketDataContractTests(unittest.TestCase):
    def test_valid_quote_is_utc_traceable_and_high_quality(self):
        received = datetime(2026, 10, 1, 20, 1, tzinfo=timezone.utc)
        quote = quote_from_history("TEST", history(), received_at=received)
        self.assertEqual(quote["contract_version"], "3.0")
        self.assertEqual(quote["provider"], "yahoo_chart_v8")
        self.assertEqual(quote["currency"], "USD")
        self.assertEqual(quote["market_timestamp"], "2026-10-01T20:00:00Z")
        self.assertEqual(quote["freshness_seconds"], 60)
        self.assertFalse(quote["is_stale"])
        self.assertGreaterEqual(quote["quality_score"], 0.995)

    def test_stale_daily_quote_is_blocked(self):
        received = datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc)
        quote = quote_from_history("TEST", history(), received_at=received)
        self.assertTrue(quote["is_stale"])

    def test_invalid_ohlc_bounds_reduce_quality(self):
        df = history()
        df.loc[df.index[-1], "High"] = 50
        result = validate_ohlcv(df)
        self.assertFalse(result["valid"])
        self.assertIn("invalid_ohlc_bounds", result["issues"])
        self.assertLess(result["quality_score"], 0.95)

    def test_duplicate_timestamps_are_detected(self):
        df = history()
        df.index = list(df.index[:-1]) + [df.index[-2]]
        result = validate_ohlcv(df)
        self.assertIn("duplicate_timestamps", result["issues"])

    def test_missing_interval_is_identified(self):
        df = history(rows=10)
        # Sesiones bursátiles reales: quitar un domingo no es un hueco NYSE.
        df.index = pd.bdate_range('2026-09-14', periods=10, tz='UTC')
        df = df.drop(df.index[5])
        result = validate_ohlcv(df)
        self.assertEqual(result["expected_frequency_seconds"], 86400)
        self.assertEqual(result["gap_count"], 1)
        self.assertIn("missing_intervals:1", result["issues"])

    def test_legacy_result_is_explicitly_stale(self):
        quote = ensure_quote_contract({"Ticker": "OLD", "Price": 10})
        self.assertEqual(quote["provider"], "legacy_unknown")
        self.assertTrue(quote["is_stale"])
        self.assertEqual(quote["quality_score"], 0.0)

    def test_split_adjustment_preserves_raw_and_continuous_price(self):
        df = history(rows=2)
        df.loc[df.index[0], ["Open", "High", "Low", "Close"]] = [99, 101, 98, 100]
        df.loc[df.index[1], ["Open", "High", "Low", "Close"]] = [49, 51, 48, 50]
        adjusted = apply_adjusted_close(df, [50, 50])
        self.assertEqual(adjusted.iloc[0]["Raw_Close"], 100)
        self.assertEqual(adjusted.iloc[0]["Close"], 50)
        self.assertEqual(adjusted.iloc[1]["Close"], 50)
        self.assertTrue(adjusted.attrs["adjusted"])

    def test_provider_divergence_requires_review(self):
        primary = {"symbol": "TEST", "price": 100, "provider": "one"}
        secondary = {"symbol": "TEST", "price": 101, "provider": "two"}
        result = reconcile_quotes(primary, secondary)
        self.assertFalse(result["consistent"])
        self.assertTrue(result["requires_review"])

    def test_exchange_rate_is_versioned_and_within_intraday_window(self):
        quote_time = datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc)
        rate = exchange_rate_contract(18.5, received_at=quote_time + timedelta(minutes=14))
        rate_time = datetime.fromisoformat(rate["received_at"].replace("Z", "+00:00"))
        self.assertEqual(rate["contract_version"], "3.0")
        self.assertEqual(rate["pair"], "USD/MXN")
        self.assertLessEqual(abs((rate_time - quote_time).total_seconds()), 15 * 60)


class CrossModuleConsistencyTests(unittest.TestCase):
    def test_portfolio_reuses_price_and_rechecks_freshness(self):
        df = history()
        quote = quote_from_history(
            "TEST",
            df,
            received_at=datetime(2026, 10, 1, 20, 1, tzinfo=timezone.utc),
        )
        quote["price"] = 123.456
        with patch("portfolio_analyzer._fetch_history_raw", return_value=df), patch('market_data.utc_now', return_value=datetime(2026, 10, 9, 15, tzinfo=timezone.utc)):
            result = analyze_ticker_strategy("TEST", entry_price=100, qty=2, quote_override=quote)
        self.assertIsNone(result["error"])
        self.assertEqual(result["price"], 123.46)
        for field in ('price', 'provider', 'symbol', 'market_timestamp', 'received_at', 'quality_score'):
            self.assertEqual(result['quote'][field], quote[field])
        self.assertTrue(result['quote']['is_stale'])
        self.assertFalse(result['pnl_reliable'])
        difference_pct = abs(result["price"] - round(quote["price"], 2)) / quote["price"] * 100
        self.assertLessEqual(difference_pct, 0.10)

    def test_wrong_ticker_override_is_rejected(self):
        df = history()
        quote = quote_from_history("OTHER", df)
        with patch("portfolio_analyzer._fetch_history_raw", return_value=df):
            result = analyze_ticker_strategy("TEST", quote_override=quote)
        self.assertIn("no corresponde", result["error"])


class MissingValueContractTests(unittest.TestCase):
    def test_fundamentals_are_not_silently_rendered_as_zero(self):
        source = (VISOR / "stock_scanner.py").read_text(encoding="utf-8")
        self.assertIn("'Gross Margin':     None", source)
        self.assertIn("'Beta':             round(float(beta), 2) if beta is not None else None", source)
        self.assertIn("'Market_Cap':       info.get('marketCap')", source)

    def test_legacy_fundamentals_are_not_presented_as_verified_zero(self):
        source = (ROOT / "src" / "server.py").read_text(encoding="utf-8")
        self.assertIn("quote.get('provider') != 'legacy_unknown'", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
