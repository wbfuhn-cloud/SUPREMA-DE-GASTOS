import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(BOT_DIR))

from ml_predictor import FEATURE_NAMES, OODProfile, StockMLPredictor  # noqa: E402
from notification_config import resolve_telegram_chat_id  # noqa: E402
from stock_scanner import _SESSION  # noqa: E402


class _RawGradientBoostingLike:
    n_features_in_ = len(FEATURE_NAMES)
    feature_importances_ = np.ones(len(FEATURE_NAMES), dtype=float) / len(FEATURE_NAMES)

    def predict_proba(self, features):
        return np.asarray([[0.27, 0.73] for _ in features], dtype=float)


class RuntimeHardeningTests(unittest.TestCase):
    def test_raw_estimator_predicts_without_named_steps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            predictor = StockMLPredictor(
                db_path=str(Path(temp_dir) / "missing.db"),
                model_path=str(Path(temp_dir) / "missing.joblib"),
            )
            predictor.model = _RawGradientBoostingLike()
            predictor.production_approved = True
            predictor.ood_profile = OODProfile(
                np.full(len(FEATURE_NAMES), -1e12),
                np.full(len(FEATURE_NAMES), 1e12),
            )
            prediction = predictor.predict_score({"score": 70, "rsi": 55, "price": 100})

        self.assertEqual(prediction["source"], "validated_ml_model")
        self.assertAlmostEqual(prediction["probability"], 0.73)
        self.assertTrue(prediction["top_features"])

    def test_yahoo_pool_supports_all_scanner_workers(self):
        adapter = _SESSION.get_adapter("https://")
        self.assertGreaterEqual(adapter._pool_maxsize, 40)
        self.assertTrue(adapter._pool_block)

    def test_telegram_file_is_optional_and_root_file_is_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "chat_id.txt").write_text("123456\n", encoding="utf-8")
            self.assertEqual(resolve_telegram_chat_id(temp_dir, "", ""), "")
            self.assertEqual(resolve_telegram_chat_id(temp_dir, "token", ""), "123456")
            self.assertEqual(resolve_telegram_chat_id(temp_dir, "token", "configured"), "configured")
        server_source = (ROOT / "src" / "server.py").read_text(encoding="utf-8")
        self.assertNotIn('Error enviando notificacion bolsa: {e}', server_source)
        self.assertNotIn('Error Telegram: {res.text}', server_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
