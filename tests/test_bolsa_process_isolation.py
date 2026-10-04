import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bolsa_worker import detect_compute_backend  # noqa: E402
from src import server  # noqa: E402


class BolsaProcessIsolationTests(unittest.TestCase):
    def test_current_model_reports_cpu_without_hiding_detected_gpu(self):
        compute = detect_compute_backend()
        self.assertEqual(compute["backend"], "cpu")
        self.assertEqual(compute["reason"], "sklearn_gradient_boosting_cpu_only")
        self.assertIn("available", compute["gpu"])

    def test_main_application_disables_in_process_bolsa_jobs(self):
        app_source = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("start_bolsa_worker()", app_source)
        self.assertIn("'start_jobs': False", app_source)
        self.assertIn("'start_jobs': False", main_source)

    def test_worker_heartbeat_distinguishes_active_from_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            status_file = Path(temporary) / "worker.json"
            with patch.object(server, "BOLSA_WORKER_STATUS_FILE", str(status_file)):
                current = datetime.now(timezone.utc)
                status_file.write_text(json.dumps({
                    "status": "running", "heartbeat_utc": current.isoformat(), "pid": 123,
                }), encoding="utf-8")
                self.assertTrue(server._external_worker_status()["active"])

                stale = current - timedelta(minutes=2)
                status_file.write_text(json.dumps({
                    "status": "running", "heartbeat_utc": stale.isoformat(), "pid": 123,
                }), encoding="utf-8")
                self.assertFalse(server._external_worker_status()["active"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
