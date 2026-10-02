import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from error_taxonomy import ErrorRegistry, classify_error, sanitize_public_error  # noqa: E402


class ErrorHardeningTests(unittest.TestCase):
    def test_dom_network_auth_and_financial_errors_are_classified(self):
        self.assertEqual(classify_error("Cannot read properties of null (reading classList)")["category"], "DOM_NULL")
        self.assertEqual(classify_error("fetch timeout", status_code=503)["category"], "NETWORK_API")
        self.assertEqual(classify_error("No autorizado", status_code=401)["category"], "AUTH_SECURITY")
        self.assertEqual(classify_error("ticker quote unavailable")["category"], "FINANCIAL_ENGINE")

    def test_public_errors_remove_local_paths_and_apply_bounds(self):
        safe = sanitize_public_error(r"Falló C:\Users\OMEN\secret\model.joblib: detalle")
        self.assertNotIn("OMEN", safe)
        self.assertIn("ruta local oculta", safe)
        self.assertLessEqual(len(sanitize_public_error("x" * 1000)), 500)

    def test_registry_aggregates_bounded_safe_diagnostics(self):
        registry = ErrorRegistry(max_items=2)
        registry.record({"message": "null classList", "component": "bolsa-ui"})
        registry.record({"message": "HTTP 503 timeout", "component": "api"})
        registry.record({"message": "HTTP 503 timeout", "component": "api"})
        summary = registry.summary()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["by_category"], {"NETWORK_API": 2})
        self.assertEqual(len(summary["recent"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
