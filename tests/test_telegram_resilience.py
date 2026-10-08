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


if __name__ == "__main__":
    unittest.main()
