import json
import logging
import sqlite3
from contextlib import closing
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from src.diagnostics import redact, status, recent_errors, SafeLogFormatter
from src.local_expenses import read_local_expenses


class DiagnosticTests(unittest.TestCase):
    def test_cli_is_utf8_json_from_another_directory(self):
        script = Path(__file__).resolve().parents[1] / 'diagnostico.py'
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(script), 'estado', '--json'],
                cwd=directory, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout.decode('utf-8'))
        self.assertTrue(report['read_only'])
        self.assertIn('status', report)
    def test_logs_redact_raw_and_url_credentials(self):
        text = 'cfk_example123 123456789:abcdefghijklmnopqrstuvwxyz12345 Bearer private_value custom_password'
        result = redact(text, ['custom_password'])
        for secret in ('cfk_example123', '123456789:', 'private_value', 'custom_password'):
            self.assertNotIn(secret, result)

    def test_status_reports_presence_without_values(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, '.env').write_text("CLOUDFLARE_API_TOKEN='cfk_example123'\nTELEGRAM_BOT_TOKEN=secret\n")
            result = status(directory)
        self.assertEqual(result['credential_type'], 'global_api_key')
        self.assertTrue(result['configured']['TELEGRAM_BOT_TOKEN'])
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('cfk_example123', json.dumps(result))

    def test_existing_logs_and_formatter_redact_secrets(self):
        record = logging.LogRecord('test', logging.ERROR, '', 0, 'failure %s', ('private_value',), None)
        self.assertNotIn('private_value', SafeLogFormatter(['private_value']).format(record))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('CLOUDFLARE_API_TOKEN=private_value\n')
            (root / 'logs').mkdir()
            (root / 'logs' / 'app.log').write_text('INFO ignored\nERROR private_value\nWARNING warning\n')
            result = recent_errors(root, lines=1)
        self.assertEqual(result['logs/app.log']['entries'], ['WARNING warning'])

    def test_missing_database_is_never_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'missing.db')
            with self.assertRaises(FileNotFoundError):
                read_local_expenses(path)
            self.assertFalse(path.exists())

    def test_cloud_failure_renders_local_views_without_changing_database(self):
        from src import server
        from src.database import DatabaseUnavailable
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'database').mkdir()
            path = root / 'database' / 'expenses.db'
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE expenses (id INTEGER, date TEXT, total REAL, category TEXT, merchant TEXT, status TEXT, type TEXT)')
                db.execute("INSERT INTO expenses VALUES (1,'2026-09-05',10,'COMIDA','LOCAL TEST','paid','Normal')")
                db.commit()
            original = path.read_bytes()
            with patch.object(server, 'root_dir', directory), \
                    patch.object(server.db_manager, 'get_available_years', side_effect=DatabaseUnavailable('Cloud unavailable')), \
                    patch.object(server.db_manager, 'get_all_expenses', side_effect=DatabaseUnavailable('Cloud unavailable')), \
                    patch.object(server, '_get_cached_view', return_value=None):
                for route in ('/dashboard', '/transactions', '/details'):
                    response = server.app.test_client().get(route)
                    self.assertEqual(response.status_code, 200, route)
                    self.assertEqual(response.headers['X-Data-Source'], 'local-readonly')
                    self.assertIn("connect-src 'none'", response.headers['Content-Security-Policy'])
                    self.assertIn('SOLO LECTURA', response.get_data(as_text=True))
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
