import os
import sys
import unittest
from unittest.mock import Mock, patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(ROOT, "tools", "NOTIFICADOR_BOT")
if BOT not in sys.path:
    sys.path.insert(0, BOT)

from secondary_market_data import verify_quote
from signal_fusion import FusionInput, fuse_signal


class SecondaryMarketDataTests(unittest.TestCase):
    @patch("secondary_market_data.requests.get")
    def test_nasdaq_confirms_close_price(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": {"symbol": "AAPL", "marketStatus": "Open", "primaryData": {
                "lastSalePrice": "$100.40",
                "lastTradeTimestamp": "Oct 5, 2026 12:38 PM ET",
                "isRealTime": True,
            }}
        }
        get.return_value = response
        result = verify_quote({"symbol": "AAPL", "price": 100.0,
                               "provider": "yahoo_chart_v8"})
        self.assertEqual(result["status"], "confirmed")
        self.assertLess(result["difference_pct"], 1.0)

    def test_ninety_percent_quality_is_eligible_for_fusion(self):
        result = fuse_signal(FusionInput(
            symbol="TEST", horizon="swing", heuristic_score=0.1,
            heuristic_state="ESPERAR", data_quality=0.90, regime="lateral",
            price=100.0, atr=2.0,
        ))
        self.assertNotEqual(result["state"], "SIN SEÑAL")


if __name__ == "__main__":
    unittest.main()
