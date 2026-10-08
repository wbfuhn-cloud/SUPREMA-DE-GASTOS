import os
import sqlite3
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(ROOT, 'tools', 'NOTIFICADOR_BOT')
if BOT not in sys.path:
    sys.path.insert(0, BOT)

from recommendation_learner import AdaptiveLearner


class LearnerV3ConfidenceTests(unittest.TestCase):
    def test_reads_verified_v3_instead_of_empty_legacy_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            learner = AdaptiveLearner(os.path.join(tmp, 'learner.db'))
            db = learner.db
            conn = sqlite3.connect(db.db_path)
            for index in range(12):
                prediction_id = f'p{index}'
                conn.execute("""INSERT INTO predictions_v3
                    (prediction_id,symbol,market,data_timestamp,emitted_at,horizon_sessions,
                     expected_entry_session,expected_entry_policy,expected_entry_price,features_json,
                     feature_version,signal,probability,score,model_name,model_version,model_hash,
                     risk_rules_json,data_provider,quote_json,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (prediction_id, 'ABC', 'XNYS', '2026-10-01T00:00:00Z',
                     '2026-10-01T00:00:00Z', 1, '2026-10-02', 'NEXT_SESSION_OPEN', 10,
                     '{"rsi":55}', '3', 'REDUCIR', None, 20, 'heuristic', '3', 'hash',
                     '{}', 'yahoo', '{}', '2026-10-01T00:00:00Z'))
                conn.execute("""INSERT INTO prediction_results_v3
                    (prediction_id,horizon_sessions,due_session,status,net_return,
                     positive_threshold,negative_threshold,market_label)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (prediction_id, 1, '2026-10-02', 'VERIFIED', -.02, .01, -.01,
                     'SALIDA_CORRECTA' if index < 9 else 'SALIDA_INCORRECTA'))
            conn.commit(); conn.close()
            result = db.get_confidence_for_ticker('ABC', rsi=55, signal='REDUCIR')
            self.assertTrue(result['available'])
            self.assertEqual(result['source'], 'prediction_ledger_v3')
            self.assertGreaterEqual(result['sample_size'], 12)
            self.assertAlmostEqual(result['confidence'], 75.0)


if __name__ == '__main__':
    unittest.main()
