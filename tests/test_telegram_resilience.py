import logging
import os
import queue
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app import TextHandler


class TelegramResilienceTests(unittest.TestCase):
    def test_network_traceback_is_compacted_in_gui(self):
        output = queue.Queue()
        handler = TextHandler(output)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        try:
            raise OSError("getaddrinfo failed")
        except OSError:
            record = logging.LogRecord(
                "telegram.ext._utils.networkloop", logging.ERROR, __file__, 1,
                "Network Retry Loop (Bootstrap Initialize Application): Aborting.",
                (), sys.exc_info(),
            )
        handler.emit(record)
        message = output.get_nowait()
        self.assertIn("reintentando automáticamente", message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("getaddrinfo", message)


    def test_gui_hides_bot_credential_without_changing_other_handlers(self):
        output = queue.Queue()
        handler = TextHandler(output)
        record = logging.LogRecord(
            "httpx", logging.WARNING, __file__, 1,
            "HTTP Request: %s", ("https://api.telegram.org/bot123:example-secret/getUpdates",), None,
        )
        handler.emit(record)
        message = output.get_nowait()
        self.assertNotIn("example-secret", message)
        self.assertIn("bot[OCULTO]/getUpdates", message)
        self.assertIn("example-secret", record.getMessage())

    def test_email_network_failure_retries_and_recovers(self):
        from unittest.mock import Mock, patch
        from requests.exceptions import ConnectionError
        from src import monitor
        reader = Mock()
        reader.run_once.side_effect = [ConnectionError("DNS unavailable"), 0]
        stop = Mock()
        stop.is_set.side_effect = [False, False, True]
        with patch.object(monitor, 'EmailReader', return_value=reader), patch.object(monitor, 'stop_event', stop), self.assertLogs('BAZ-Monitor', level='WARNING') as logs:
            monitor.hilo_baz()
        self.assertEqual(reader.run_once.call_count, 2)
        self.assertEqual(stop.wait.call_count, 2)
        self.assertIn('Se reintentará', logs.output[0])
        self.assertNotIn('Traceback', logs.output[0])


if __name__ == "__main__":
    unittest.main()
