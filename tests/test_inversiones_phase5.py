import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VISOR = ROOT / "tools" / "NOTIFICADOR_BOT"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(VISOR))

from src.updater import GitHubReleaseUpdater  # noqa: E402
from ml_predictor import StockMLPredictor  # noqa: E402
from ml_validation import OODProfile, PurgedWalkForwardSplit, audit_legacy_artifact, phase5_approval  # noqa: E402


class FakeResponse:
    def __init__(self, payload=None, chunks=(), status=200):
        self.payload = payload
        self.chunks = chunks
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self.payload

    def iter_content(self, chunk_size=0):
        yield from self.chunks


class Phase5IntegrationTests(unittest.TestCase):
    def test_walk_forward_is_purged_and_only_complete_metrics_can_pass(self):
        folds = list(PurgedWalkForwardSplit(n_splits=3, purge=20, embargo=5, min_train_size=100).split(400))
        self.assertEqual(len(folds), 3)
        self.assertTrue(all(train.max() + 20 < test.min() for train, test in folds))
        passing = {
            "pr_auc": .42, "prevalence": .20, "precision_top_10": .60,
            "benchmark_precision_top_10": .45, "brier_score": .12,
            "prevalence_brier": .16, "ece": .04, "profitable_folds_ratio": .75,
            "worst_fold_risk_multiple": -1.2, "eligible_model_usage_ratio": .97,
            "reproducible": True,
        }
        self.assertTrue(phase5_approval(passing)["approved"])

    def test_legacy_model_is_experiment_only_and_ood_is_explicit(self):
        audit = audit_legacy_artifact({"samples_total": 4001, "auc_score": 74.78}, 0)
        self.assertEqual(audit["decision"], "experiment_only")
        predictor = StockMLPredictor()
        prediction = predictor.predict_score({"score": 70})
        self.assertEqual(prediction["source"], "heuristic_fallback")
        self.assertIsNone(prediction["calibrated_probability"])
        profile = OODProfile.from_training(np.array([[0.0, 1.0], [1.0, 2.0], [0.5, 1.5]]))
        self.assertEqual(profile.detect(np.array([99.0, 1.5]))[0], True)

    def test_startup_updater_downloads_new_github_release_without_installing(self):
        payload = b"portable-update"
        release = {
            "tag_name": "v99.0.0", "html_url": "https://github.com/acme/app/releases/tag/v99.0.0",
            "assets": [{"name": "app.zip", "size": len(payload), "browser_download_url": "https://example/app.zip"}],
        }

        def fake_get(url, **_kwargs):
            return FakeResponse(payload=release) if "api.github.com" in url else FakeResponse(chunks=[payload])

        with tempfile.TemporaryDirectory() as directory:
            result = GitHubReleaseUpdater("acme/app", Path(directory), fake_get).check_and_download()
            self.assertEqual(result.status, "downloaded")
            self.assertEqual(Path(result.download_path).read_bytes(), payload)
            self.assertTrue(Path(result.download_path + ".sha256").exists())
            status = json.loads((Path(directory) / "update-status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["latest_version"], "99.0.0")
        self.assertIn("start_background_update_check()", (ROOT / "src" / "app.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
