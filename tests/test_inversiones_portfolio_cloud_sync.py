import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from portfolio_sync import PORTFOLIO_SETTING_KEY, PortfolioSync  # noqa: E402


class _Config:
    def __init__(self, portfolio=None):
        self.config = {"portfolio": portfolio or {}}
        self.saved = 0

    def get_portfolio(self):
        return self.config["portfolio"]

    def save_config(self):
        self.saved += 1
        return True


class _CloudStore:
    storage_mode = "cloud"

    def __init__(self, value=None):
        self.value = value
        self.available = True

    def get_setting_status(self, key):
        assert key == PORTFOLIO_SETTING_KEY
        return self.available, self.value

    def set_setting(self, key, value):
        assert key == PORTFOLIO_SETTING_KEY
        if not self.available:
            return False, "Nube no disponible"
        self.value = value
        return True, "Guardado en D1"


class PortfolioCloudSyncTests(unittest.TestCase):
    def test_first_load_migrates_existing_local_portfolio_to_cloud(self):
        store = _CloudStore()
        sync = PortfolioSync(_Config({"aapl": {"qty": 2, "avg_price": 100}}), store)

        portfolio, metadata = sync.load(migrate_local=True)

        self.assertIn("AAPL", portfolio)
        self.assertTrue(metadata["synchronized"])
        self.assertEqual(json.loads(store.value)["portfolio"]["AAPL"]["qty"], 2.0)

    def test_update_on_one_device_is_loaded_by_another_device(self):
        store = _CloudStore()
        first = PortfolioSync(_Config(), store)
        second = PortfolioSync(_Config(), store)

        _portfolio, write_metadata = first.update("msft", 3, 410)
        loaded, read_metadata = second.load()

        self.assertTrue(write_metadata["synchronized"])
        self.assertTrue(read_metadata["synchronized"])
        self.assertEqual(loaded["MSFT"]["avg_price"], 410.0)

    def test_cloud_failure_does_not_report_or_apply_unsynchronized_write(self):
        initial = json.dumps({"portfolio": {"NVDA": {"qty": 1, "avg_price": 150}}})
        store = _CloudStore(initial)
        config = _Config()
        sync = PortfolioSync(config, store)
        sync.load()
        store.available = False

        portfolio, metadata = sync.update("TSLA", 4, 300)

        self.assertFalse(metadata["synchronized"])
        self.assertNotIn("TSLA", portfolio)
        self.assertEqual(set(config.get_portfolio()), {"NVDA"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
