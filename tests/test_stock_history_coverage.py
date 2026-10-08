"""Pruebas del mínimo histórico exigido por el escáner bursátil."""

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(VISOR))

from stock_scanner import (  # noqa: E402
    HISTORY_DOWNLOAD_PERIOD,
    MIN_HISTORY_CALENDAR_DAYS,
    MIN_HISTORY_SESSIONS,
    FULL_TRADING_YEAR_SESSIONS,
    history_coverage,
    build_holding_outlook,
)


class HistoricalCoverageTests(unittest.TestCase):
    def test_download_requests_more_than_the_required_minimum(self):
        self.assertEqual(HISTORY_DOWNLOAD_PERIOD, "2y")
        self.assertEqual(MIN_HISTORY_CALENDAR_DAYS, 365)
        self.assertEqual(MIN_HISTORY_SESSIONS, 200)
        self.assertEqual(FULL_TRADING_YEAR_SESSIONS, 250)

    def test_accepts_at_least_one_calendar_year_and_200_sessions(self):
        index = pd.date_range("2025-01-02", periods=270, freq="B", tz="UTC")
        frame = pd.DataFrame({"Close": range(len(index))}, index=index)
        coverage = history_coverage(frame)
        self.assertTrue(coverage["eligible"])
        self.assertGreaterEqual(coverage["calendar_days"], 365)
        self.assertEqual(coverage["sessions"], 270)

    def test_rejects_many_rows_without_one_year_of_elapsed_history(self):
        index = pd.date_range("2026-01-02", periods=200, freq="D", tz="UTC")
        frame = pd.DataFrame({"Close": range(len(index))}, index=index)
        coverage = history_coverage(frame)
        self.assertFalse(coverage["eligible"])
        self.assertEqual(coverage["sessions"], 200)
        self.assertLess(coverage["calendar_days"], 365)

    def test_rejects_one_year_with_too_few_market_sessions(self):
        index = pd.date_range("2025-01-01", "2026-01-02", periods=100, tz="UTC")
        frame = pd.DataFrame({"Close": range(len(index))}, index=index)
        coverage = history_coverage(frame)
        self.assertFalse(coverage["eligible"])
        self.assertGreaterEqual(coverage["calendar_days"], 365)
        self.assertEqual(coverage["sessions"], 100)

    def test_holding_outlook_covers_one_three_and_six_months(self):
        close = pd.Series(range(100, 300), dtype=float)
        outlook = build_holding_outlook(close, "COMPRAR")
        self.assertTrue(outlook["available"])
        self.assertEqual(
            {item["sessions"] for item in outlook["horizons"].values()},
            {21, 63, 126},
        )
        self.assertTrue(all(item["verdict"] == "CANDIDATA" for item in outlook["horizons"].values()))

    def test_leveraged_asset_is_never_labeled_purchase_candidate(self):
        close = pd.Series(range(100, 300), dtype=float)
        outlook = build_holding_outlook(close, "COMPRAR", is_leveraged=True)
        self.assertTrue(all(item["verdict"] == "OBSERVAR" for item in outlook["horizons"].values()))


if __name__ == "__main__":
    unittest.main()
