import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import settings
from src.database import CloudflareDatabaseManager, DatabaseUnavailable, get_database_manager


class StartupDataTests(unittest.TestCase):
    def test_auth_failure_does_not_repeat_cloud_request_for_every_page(self):
        manager = CloudflareDatabaseManager('account', 'database', 'token')
        with patch('src.database.httpx.post', return_value=Mock(status_code=401)) as post:
            for _ in range(2):
                with self.assertRaises(DatabaseUnavailable):
                    manager.get_all_expenses()
            post.assert_called_once()
    def test_settings_use_installation_file_and_preserve_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / '.env'
            env.write_text('STARTUP_TEST_VALUE=file\nSTARTUP_TEST_NEW=loaded\n')
            with patch.object(settings, 'ENV_FILE', env), patch.dict(os.environ, {'STARTUP_TEST_VALUE': 'environment'}, clear=True):
                settings.load_settings()
                self.assertEqual(os.environ['STARTUP_TEST_VALUE'], 'environment')
                self.assertEqual(os.environ['STARTUP_TEST_NEW'], 'loaded')

    def test_partial_cloud_configuration_does_not_select_empty_local_database(self):
        with patch('src.database.load_settings'), patch.dict(os.environ, {'CLOUDFLARE_ACCOUNT_ID': 'account'}, clear=True):
            with self.assertRaises(DatabaseUnavailable):
                get_database_manager()

    def test_denied_cloud_query_does_not_report_empty_database_or_expose_response(self):
        manager = CloudflareDatabaseManager('account', 'database', 'token')
        with patch('src.database.httpx.post', return_value=Mock(status_code=403, text='sensitive-response')):
            with self.assertRaises(DatabaseUnavailable) as result:
                manager.get_all_expenses()
        self.assertIn('403', str(result.exception))
        self.assertNotIn('sensitive-response', str(result.exception))

    def test_successful_empty_query_remains_empty(self):
        manager = CloudflareDatabaseManager('account', 'database', 'token')
        response = Mock(status_code=200)
        response.json.return_value = {'success': True, 'result': [{'results': []}]}
        with patch('src.database.httpx.post', return_value=response):
            self.assertEqual(manager.get_all_expenses(), [])

    def test_dashboard_displays_unavailable_instead_of_no_expenses(self):
        from src import server
        with tempfile.TemporaryDirectory() as directory, patch.object(server, 'root_dir', directory), patch.object(server.db_manager, 'get_available_years', side_effect=DatabaseUnavailable('Connection unavailable')):
            response = server.app.test_client().get('/dashboard')
        self.assertEqual(response.status_code, 503)
        self.assertIn('No se pudieron cargar los gastos', response.get_data(as_text=True))
        self.assertNotIn('La base de datos está vacía', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
