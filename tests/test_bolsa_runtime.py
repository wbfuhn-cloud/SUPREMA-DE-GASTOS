import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch, Mock
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools' / 'NOTIFICADOR_BOT'))
from src import bolsa_worker
from src.json_provider import FiniteJSONProvider
from flask import Flask
from market_data import ensure_quote_contract
from paper_trading import PaperTradingLedger
from prediction_ledger import NyseCalendar
from src.service_supervisor import BolsaSupervisor
from portfolio_status import classify_portfolio_position


class RuntimeTests(unittest.TestCase):
    def test_supervisor_restarts_failed_worker(self):
        supervisor = BolsaSupervisor.__new__(BolsaSupervisor)
        supervisor._stop = Mock()
        supervisor._stop.wait.side_effect = [False, True]
        supervisor._stop.is_set.return_value = False
        supervisor._lock = threading.Lock()
        supervisor.process = Mock()
        supervisor.process.poll.return_value = 1
        replacement = Mock()
        with patch('src.service_supervisor._spawn_bolsa_worker', return_value=replacement) as spawn:
            supervisor._watch()
            spawn.assert_called_once()
        self.assertIs(supervisor.process, replacement)

    def test_unvalidated_portfolio_does_not_instruct_trading(self):
        for pnl in (-15, -5, 20):
            result = classify_portfolio_position(pl_pct=pnl, signal_state='COMPRAR',
                signal_eligible=True, data_quality=1, quote_stale=False)
            self.assertIn('No hay una recomendación', result['summary'])
            self.assertNotIn('VENDE', result['summary'])
            self.assertNotIn('AGUANTA', result['summary'])
        stale = classify_portfolio_position(pl_pct=-20, signal_state='SALIR',
            signal_eligible=True, data_quality=1, quote_stale=True)
        self.assertFalse(stale['pnl_reliable'])

    def test_windows_sharing_violation_retries_without_losing_last_status(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'status.json'
            target.write_text('{"status":"previous"}')
            real_replace = bolsa_worker.os.replace
            calls = []
            def replace(src, dest):
                calls.append(src)
                if len(calls) < 3:
                    raise PermissionError('sharing violation')
                return real_replace(src, dest)
            with patch.object(bolsa_worker, 'STATUS_FILE', target), patch.object(bolsa_worker.os, 'replace', side_effect=replace), patch.object(bolsa_worker.time, 'sleep'):
                self.assertTrue(bolsa_worker._write_status({'status': 'running'}))
            self.assertEqual(json.loads(target.read_text())['status'], 'running')
            self.assertEqual(len(calls), 3)
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])

    def test_persistent_write_failure_does_not_kill_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'status.json'
            target.write_text('{"status":"previous"}')
            with patch.object(bolsa_worker, 'STATUS_FILE', target), patch.object(bolsa_worker.os, 'replace', side_effect=PermissionError()), patch.object(bolsa_worker.time, 'sleep'):
                self.assertFalse(bolsa_worker._write_status({'status': 'running'}))
            self.assertEqual(json.loads(target.read_text())['status'], 'previous')
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])

    def test_cached_fresh_flag_expires_without_mutating_snapshot(self):
        quote = {'contract_version': '3.0', 'interval': '1d', 'is_stale': False,
                 'market_timestamp': '2026-10-08T13:30:00Z', 'received_at': '2026-10-08T14:44:00Z'}
        current = ensure_quote_contract({'Quote': quote}, datetime(2026, 10, 9, 15, tzinfo=timezone.utc))
        self.assertTrue(current['is_stale'])
        self.assertFalse(quote['is_stale'])
        self.assertGreater(current['freshness_seconds'], 86400)

    def test_daily_bar_open_is_not_mistaken_for_download_time(self):
        quote = {'contract_version': '3.0', 'interval': '1d', 'market_timestamp': '2026-10-09T13:30:00Z', 'received_at': '2026-10-09T15:00:00Z'}
        self.assertFalse(ensure_quote_contract({'Quote': quote}, datetime(2026, 10, 9, 15, 1, tzinfo=timezone.utc))['is_stale'])

    def test_api_json_is_strict_and_preserves_text(self):
        app = Flask(__name__)
        provider = FiniteJSONProvider(app)
        raw = provider.dumps({'nested': [float('nan'), float('inf')], 'label': 'NaN'})
        data = json.loads(raw, parse_constant=lambda x: self.fail(x))
        self.assertEqual(data, {'nested': [None, None], 'label': 'NaN'})

    def test_sessions_recover_legacy_regular_label_and_exclude_ineligible(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperTradingLedger(Path(directory) / 'paper.db')
            for day in (8, 9):
                ledger.append_signal({'decision_hash': str(day), 'ticker': 'TEST', 'signal': 'SIN SEÑAL',
                                      'horizon': 'swing', 'model_version': 'test', 'rules_version': 'test',
                                      'emitted_at_utc': f'2026-10-{day:02}T15:00:00Z', 'market_session': 'regular',
                                      'data_quality': .6}, 'protocol')
            with ledger._connect() as db:
                db.execute("UPDATE paper_signals SET market_session='regular'")
            metrics = ledger.metrics()
            self.assertEqual(metrics['market_sessions'], 2)
            self.assertEqual(metrics['observed_signals'], 2)
            self.assertEqual(metrics['eligible_signals'], 0)

    def test_extraordinary_exchange_closure(self):
        self.assertFalse(NyseCalendar().is_session(date(2025, 1, 9)))


if __name__ == '__main__':
    unittest.main()
