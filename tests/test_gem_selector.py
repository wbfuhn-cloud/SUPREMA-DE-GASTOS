import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(ROOT, "tools", "NOTIFICADOR_BOT")
if BOT not in sys.path:
    sys.path.insert(0, BOT)

from gem_selector import select_daily_gems


def row(ticker, *, volume=1.2, rsi=55, state="MANTENER/ESPERAR", eligible=True):
    return {"Ticker": ticker, "Vol_Ratio": volume, "RSI": rsi,
            "MACD": 1.0, "MACD_Signal": 0.5, "MACD_Hist": 0.5,
            "Market_Cap": 10_000_000_000, "Is_Leveraged": False,
            "Signal_State": state, "Signal_Eligible": eligible}


class GemSelectorTests(unittest.TestCase):
    def test_unknown_capitalization_cannot_confirm_a_gem(self):
        for missing in (None, 0, float('nan')):
            candidate = row('UNKNOWN')
            candidate['Market_Cap'] = missing
            self.assertEqual(select_daily_gems([candidate]), [])

    def test_matches_web_rules_and_excludes_false_gems(self):
        results = [row("VST", volume=1.28, rsi=57.38),
                   row("PTC", volume=7.06, rsi=80.53, state="REDUCIR"),
                   row("ACN", volume=.38, rsi=56.81),
                   row("WBD", volume=.53, rsi=75.31),
                   row("BAD", eligible=False)]
        self.assertEqual([item["Ticker"] for item in select_daily_gems(results)], ["VST"])

    def test_orders_by_abnormal_volume(self):
        results = [row("LOW", volume=1.2), row("HIGH", volume=2.5)]
        self.assertEqual([item["Ticker"] for item in select_daily_gems(results)],
                         ["HIGH", "LOW"])


if __name__ == "__main__":
    unittest.main()
