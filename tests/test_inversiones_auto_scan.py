import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from auto_scan_schedule import auto_scan_due, next_nyse_open, nyse_market_is_open  # noqa: E402


NY = ZoneInfo("America/New_York")


class AutoScanScheduleTests(unittest.TestCase):
    def test_scheduler_accepts_regular_session_and_respects_interval(self):
        now = datetime(2026, 10, 2, 10, 0, tzinfo=NY)
        self.assertTrue(nyse_market_is_open(now))
        self.assertTrue(auto_scan_due(now, None, 60))
        self.assertFalse(auto_scan_due(now, now - timedelta(minutes=30), 60))

    def test_scheduler_rejects_after_hours_weekends_and_holidays(self):
        self.assertFalse(nyse_market_is_open(datetime(2026, 10, 2, 18, 0, tzinfo=NY)))
        self.assertFalse(nyse_market_is_open(datetime(2026, 10, 3, 11, 0, tzinfo=NY)))
        self.assertFalse(nyse_market_is_open(datetime(2026, 12, 25, 11, 0, tzinfo=NY)))

    def test_next_open_uses_nyse_calendar(self):
        friday_after_close = datetime(2026, 10, 2, 18, 0, tzinfo=NY)
        next_open = next_nyse_open(friday_after_close).astimezone(NY)
        self.assertEqual(next_open, datetime(2026, 10, 5, 9, 30, tzinfo=NY))
        html = (ROOT / "tools" / "NOTIFICADOR_BOT" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "tools" / "NOTIFICADOR_BOT" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('id="btn-start"', html)
        self.assertNotIn('id="btn-stop"', html)
        self.assertIn("IA AUTOMÁTICA · SERVICIO PERMANENTE", html)
        self.assertIn("if (btnStart) btnStart.disabled", js)


if __name__ == "__main__":
    unittest.main(verbosity=2)
