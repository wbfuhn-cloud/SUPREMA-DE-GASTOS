import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.app import BotGUI


class WebStartupTests(unittest.TestCase):
    def test_web_starts_before_failed_telegram_initialization(self):
        events = []

        class Thread:
            def __init__(self, target, **kwargs):
                self.target = target
            def start(self):
                if self.target.__name__ == 'background_init':
                    self.target()
                else:
                    events.append('web_started')
            def is_alive(self):
                return False

        gui = SimpleNamespace(
            bot_thread=None, web_thread=None, web_port=None,
            stop_event=Mock(), start_button=Mock(), stop_button=Mock(),
            status_label=Mock(), after=Mock(), token='test', google_key='test',
            pause_services=Mock(), resume_services=Mock(),
            bolsa_worker_process=None, _reset_ui=Mock(), start_heartbeat=Mock(),
        )
        def fail_bot(*args, **kwargs):
            events.append('bot_attempted')
            raise RuntimeError('Telegram unavailable')
        with patch('src.app.threading.Thread', Thread), patch('src.app.socket.socket'), \
                patch('src.app.get_local_ip', return_value='127.0.0.1'), \
                patch('src.app.Config.validate'), patch('src.app.ExpenseBot', side_effect=fail_bot), \
                patch('src.app.prevent_sleep'), self.assertLogs(level='ERROR'):
            BotGUI.start_bot(gui)
        self.assertEqual(events, ['web_started', 'bot_attempted'])
        self.assertIsNotNone(gui.web_thread)


if __name__ == '__main__':
    unittest.main()
