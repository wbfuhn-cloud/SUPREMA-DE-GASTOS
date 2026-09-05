"""
recommendation_learner.py — Motor de aprendizaje adaptativo para recomendaciones de bolsa.

Registra recomendaciones, verifica resultados al día siguiente, y ajusta
dinámicamente los pesos del scoring basándose en aciertos/errores históricos.

Filosofía: Pesos adaptativos con retroalimentación — no redes neuronales,
sino un enfoque pragmático que mejora con cada ciclo de escaneo.
"""
import sqlite3
import json
import os
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Pesos por defecto (punto de partida) ─────────────────────────────────────
DEFAULT_WEIGHTS: Dict[str, float] = {
    'rsi_optimal':      1.0,   # RSI en zona ideal (40-60)
    'rsi_extreme_low':  1.0,   # RSI sobrevendido (<30)  → señal de compra
    'trend_sma':        1.0,   # Price > SMA50 > SMA200
    'macd_bullish':     1.0,   # MACD > Signal + histograma positivo
    'volume_high':      1.0,   # Volumen > 2M
    'volume_ratio':     1.0,   # Vol ratio alto (>1.5x)
    'market_cap_large': 1.0,   # Cap > 10B
    'bb_oversold':      1.0,   # Precio bajo la banda inferior (oversold)
    'bb_overbought':    1.0,   # Precio sobre la banda superior (overbought) — penalizable
}

# Rango permitido de pesos
WEIGHT_MIN = 0.20
WEIGHT_MAX = 2.50

# Umbrales de resultado
THRESHOLD_BAD_SEVERE  = -15.0   # Caída ≥15% → penalización fuerte
THRESHOLD_BAD_MILD    = -5.0    # Caída 5-15% → penalización leve
THRESHOLD_GOOD_MILD   =  2.0    # Subida 2-5% → recompensa leve
THRESHOLD_GOOD_STRONG =  5.0    # Subida ≥5%  → recompensa fuerte

# Factores de ajuste
PENALTY_FACTOR_SEVERE  = 0.82   # Reducir peso 18% en error grave
PENALTY_FACTOR_MILD    = 0.93   # Reducir peso 7% en error leve
REWARD_FACTOR_STRONG   = 1.08   # Aumentar peso 8% en acierto fuerte
REWARD_FACTOR_MILD     = 1.03   # Aumentar peso 3% en acierto leve
DECAY_FACTOR_WEEKLY    = 0.985  # Decay semanal para no anclarse al pasado

# ── Base de datos SQLite ─────────────────────────────────────────────────────
DB_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = DB_DIR / "learner.db"


class RecommendationDB:
    """Gestiona la base de datos SQLite del sistema de aprendizaje."""

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """Crea las tablas si no existen."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    scan_date TEXT NOT NULL,        -- Fecha del escaneo (YYYY-MM-DD)
                    score REAL NOT NULL,
                    viability TEXT,
                    price_at_rec REAL NOT NULL,      -- Precio al momento de la recomendación
                    rsi REAL,
                    macd REAL,
                    macd_signal REAL,
                    macd_hist REAL,
                    bb_upper REAL,
                    bb_lower REAL,
                    vol_ratio REAL,
                    volatility_pct REAL,
                    market_cap REAL,
                    sector TEXT,
                    -- Indicadores activos (JSON: lista de strings con los indicadores que contribuyeron al score)
                    active_indicators TEXT,
                    -- Resultado
                    verified INTEGER DEFAULT 0,      -- 0=pendiente, 1=verificado
                    price_next_day REAL,              -- Precio al día siguiente
                    price_3_days REAL,                -- Precio a 3 días
                    price_7_days REAL,                -- Precio a 7 días
                    change_pct_1d REAL,               -- % cambio 1 día
                    change_pct_3d REAL,               -- % cambio 3 días
                    change_pct_7d REAL,               -- % cambio 7 días
                    outcome TEXT,                     -- 'good', 'bad_mild', 'bad_severe', 'neutral'
                    user_feedback TEXT,               -- Feedback manual del usuario
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS adaptive_weights (
                    indicator TEXT PRIMARY KEY,
                    weight REAL NOT NULL DEFAULT 1.0,
                    adjustments_count INTEGER DEFAULT 0,
                    last_adjusted TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS weight_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    indicator TEXT NOT NULL,
                    old_weight REAL,
                    new_weight REAL,
                    reason TEXT,                      -- 'penalty_severe', 'penalty_mild', 'reward', 'decay'
                    trigger_ticker TEXT,               -- Qué ticker causó el ajuste
                    trigger_change_pct REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sector_performance (
                    sector TEXT PRIMARY KEY,
                    total_recommendations INTEGER DEFAULT 0,
                    good_outcomes INTEGER DEFAULT 0,
                    bad_outcomes INTEGER DEFAULT 0,
                    avg_change_1d REAL DEFAULT 0,
                    sector_modifier REAL DEFAULT 1.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS live_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    price REAL NOT NULL,
                    signal_type TEXT NOT NULL,      -- 'COMPRA' o 'VENTA'
                    trigger_reason TEXT,
                    ai_confidence REAL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_rec_ticker ON recommendations(ticker);
                CREATE INDEX IF NOT EXISTS idx_rec_date ON recommendations(scan_date);
                CREATE INDEX IF NOT EXISTS idx_rec_verified ON recommendations(verified);
                CREATE INDEX IF NOT EXISTS idx_rec_outcome ON recommendations(outcome);
            """)
            conn.commit()

            # Insertar pesos por defecto si la tabla está vacía
            cursor = conn.execute("SELECT COUNT(*) FROM adaptive_weights")
            if cursor.fetchone()[0] == 0:
                for indicator, weight in DEFAULT_WEIGHTS.items():
                    conn.execute(
                        "INSERT INTO adaptive_weights (indicator, weight) VALUES (?, ?)",
                        (indicator, weight)
                    )
                conn.commit()
                logger.info("🧠 Pesos adaptativos inicializados con valores por defecto.")

        except Exception as e:
            logger.error(f"Error inicializando DB del learner: {e}")
        finally:
            conn.close()

    # ── CRUD: Recomendaciones ──────────────────────────────────────────────────

    def record_recommendation(self, ticker: str, score: float, price: float,
                               indicators: dict, active_indicators: list,
                               viability: str = '') -> int:
        """Registra una recomendación nueva."""
        conn = self._get_conn()
        try:
            today = datetime.now().strftime('%Y-%m-%d')

            # No duplicar: si ya existe para hoy, actualizar
            existing = conn.execute(
                "SELECT id FROM recommendations WHERE ticker=? AND scan_date=?",
                (ticker, today)
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE recommendations SET
                        score=?, price_at_rec=?, rsi=?, macd=?, macd_signal=?,
                        macd_hist=?, bb_upper=?, bb_lower=?, vol_ratio=?,
                        volatility_pct=?, market_cap=?, sector=?,
                        active_indicators=?, viability=?
                    WHERE id=?
                """, (
                    score, price,
                    indicators.get('rsi'), indicators.get('macd'),
                    indicators.get('macd_signal'), indicators.get('macd_hist'),
                    indicators.get('bb_upper'), indicators.get('bb_lower'),
                    indicators.get('vol_ratio'), indicators.get('volatility_pct'),
                    indicators.get('market_cap'), indicators.get('sector'),
                    json.dumps(active_indicators), viability,
                    existing['id']
                ))
                conn.commit()
                return existing['id']

            cursor = conn.execute("""
                INSERT INTO recommendations (
                    ticker, scan_date, score, price_at_rec, rsi, macd, macd_signal,
                    macd_hist, bb_upper, bb_lower, vol_ratio, volatility_pct,
                    market_cap, sector, active_indicators, viability
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, today, score, price,
                indicators.get('rsi'), indicators.get('macd'),
                indicators.get('macd_signal'), indicators.get('macd_hist'),
                indicators.get('bb_upper'), indicators.get('bb_lower'),
                indicators.get('vol_ratio'), indicators.get('volatility_pct'),
                indicators.get('market_cap'), indicators.get('sector'),
                json.dumps(active_indicators), viability
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error registrando recomendación para {ticker}: {e}")
            return -1
        finally:
            conn.close()

    def get_pending_verifications(self, min_age_days: int = 1) -> List[dict]:
        """Obtiene recomendaciones no verificadas que tienen al menos N días."""
        conn = self._get_conn()
        try:
            cutoff = (datetime.now() - timedelta(days=min_age_days)).strftime('%Y-%m-%d')
            rows = conn.execute("""
                SELECT * FROM recommendations
                WHERE verified = 0 AND scan_date <= ?
                ORDER BY scan_date ASC
                LIMIT 200
            """, (cutoff,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_verification(self, rec_id: int, price_1d: float = None,
                             price_3d: float = None, price_7d: float = None,
                             price_at_rec: float = 0):
        """Actualiza una recomendación con los precios verificados."""
        conn = self._get_conn()
        try:
            change_1d = ((price_1d / price_at_rec) - 1) * 100 if price_1d and price_at_rec else None
            change_3d = ((price_3d / price_at_rec) - 1) * 100 if price_3d and price_at_rec else None
            change_7d = ((price_7d / price_at_rec) - 1) * 100 if price_7d and price_at_rec else None

            # Determinar outcome basado en la peor caída encontrada
            outcome = 'neutral'
            reference_change = change_1d  # Primero verificar 1 día

            if reference_change is not None:
                if reference_change <= THRESHOLD_BAD_SEVERE:
                    outcome = 'bad_severe'
                elif reference_change <= THRESHOLD_BAD_MILD:
                    outcome = 'bad_mild'
                elif reference_change >= THRESHOLD_GOOD_STRONG:
                    outcome = 'good_strong'
                elif reference_change >= THRESHOLD_GOOD_MILD:
                    outcome = 'good_mild'

            conn.execute("""
                UPDATE recommendations SET
                    verified = 1,
                    price_next_day = ?,
                    price_3_days = ?,
                    price_7_days = ?,
                    change_pct_1d = ?,
                    change_pct_3d = ?,
                    change_pct_7d = ?,
                    outcome = ?
                WHERE id = ?
            """, (price_1d, price_3d, price_7d, change_1d, change_3d, change_7d,
                  outcome, rec_id))
            conn.commit()
            return outcome, change_1d
        except Exception as e:
            logger.error(f"Error actualizando verificación {rec_id}: {e}")
            return 'neutral', 0
        finally:
            conn.close()

    def record_user_feedback(self, rec_id: int = None, ticker: str = None,
                              feedback: str = 'bad'):
        """Registra feedback manual del usuario."""
        conn = self._get_conn()
        try:
            if rec_id:
                conn.execute(
                    "UPDATE recommendations SET user_feedback=? WHERE id=?",
                    (feedback, rec_id)
                )
            elif ticker:
                # Marcar la más reciente para ese ticker
                conn.execute("""
                    UPDATE recommendations SET user_feedback=?
                    WHERE id = (
                        SELECT id FROM recommendations
                        WHERE ticker=? ORDER BY scan_date DESC LIMIT 1
                    )
                """, (feedback, ticker))
            conn.commit()
        finally:
            conn.close()

    # ── CRUD: Pesos adaptativos ────────────────────────────────────────────────

    def get_weights(self) -> Dict[str, float]:
        """Retorna los pesos adaptativos actuales."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT indicator, weight FROM adaptive_weights").fetchall()
            weights = {r['indicator']: r['weight'] for r in rows}
            # Complementar con defaults si faltan
            for k, v in DEFAULT_WEIGHTS.items():
                if k not in weights:
                    weights[k] = v
            return weights
        finally:
            conn.close()

    def adjust_weight(self, indicator: str, factor: float, reason: str,
                       trigger_ticker: str = '', trigger_change: float = 0):
        """Ajusta un peso multiplicándolo por el factor dado."""
        conn = self._get_conn()
        try:
            current = conn.execute(
                "SELECT weight, adjustments_count FROM adaptive_weights WHERE indicator=?",
                (indicator,)
            ).fetchone()

            if not current:
                old_w = DEFAULT_WEIGHTS.get(indicator, 1.0)
                conn.execute(
                    "INSERT INTO adaptive_weights (indicator, weight) VALUES (?, ?)",
                    (indicator, old_w)
                )
                conn.commit()
                count = 0
            else:
                old_w = current['weight']
                count = current['adjustments_count']

            new_w = max(WEIGHT_MIN, min(WEIGHT_MAX, old_w * factor))
            now = datetime.now().isoformat()

            conn.execute("""
                UPDATE adaptive_weights
                SET weight=?, adjustments_count=?, last_adjusted=?
                WHERE indicator=?
            """, (round(new_w, 4), count + 1, now, indicator))

            conn.execute("""
                INSERT INTO weight_history (indicator, old_weight, new_weight, reason,
                                            trigger_ticker, trigger_change_pct)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (indicator, round(old_w, 4), round(new_w, 4), reason,
                  trigger_ticker, trigger_change))

            conn.commit()
            logger.info(f"🧠 Peso '{indicator}': {old_w:.3f} → {new_w:.3f} ({reason}, {trigger_ticker})")
        except Exception as e:
            logger.error(f"Error ajustando peso {indicator}: {e}")
        finally:
            conn.close()

    def apply_weekly_decay(self):
        """Aplica decay semanal a todos los pesos para evitar anclaje."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT indicator, weight FROM adaptive_weights").fetchall()
            for r in rows:
                # Decay hacia 1.0 (punto neutral)
                current = r['weight']
                if current > 1.0:
                    new_w = max(1.0, current * DECAY_FACTOR_WEEKLY)
                elif current < 1.0:
                    new_w = min(1.0, current / DECAY_FACTOR_WEEKLY)
                else:
                    new_w = 1.0

                if abs(new_w - current) > 0.001:
                    conn.execute(
                        "UPDATE adaptive_weights SET weight=? WHERE indicator=?",
                        (round(new_w, 4), r['indicator'])
                    )
            conn.commit()
        finally:
            conn.close()

    # ── Estadísticas ───────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Retorna estadísticas generales del learner."""
        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) c FROM recommendations").fetchone()['c']
            verified = conn.execute(
                "SELECT COUNT(*) c FROM recommendations WHERE verified=1"
            ).fetchone()['c']
            good = conn.execute(
                "SELECT COUNT(*) c FROM recommendations WHERE outcome IN ('good_mild','good_strong')"
            ).fetchone()['c']
            bad_mild = conn.execute(
                "SELECT COUNT(*) c FROM recommendations WHERE outcome='bad_mild'"
            ).fetchone()['c']
            bad_severe = conn.execute(
                "SELECT COUNT(*) c FROM recommendations WHERE outcome='bad_severe'"
            ).fetchone()['c']
            neutral = conn.execute(
                "SELECT COUNT(*) c FROM recommendations WHERE outcome='neutral'"
            ).fetchone()['c']
            pending = conn.execute(
                "SELECT COUNT(*) c FROM recommendations WHERE verified=0"
            ).fetchone()['c']

            # Precisión (accuracy)
            accuracy = (good / verified * 100) if verified > 0 else 0

            # Promedio de cambio
            avg_change = conn.execute(
                "SELECT AVG(change_pct_1d) a FROM recommendations WHERE verified=1 AND change_pct_1d IS NOT NULL"
            ).fetchone()['a'] or 0

            weights = self.get_weights()
            adjustments = conn.execute(
                "SELECT COUNT(*) c FROM weight_history"
            ).fetchone()['c']

            return {
                'total_recommendations': total,
                'verified': verified,
                'pending': pending,
                'good_outcomes': good,
                'bad_mild': bad_mild,
                'bad_severe': bad_severe,
                'neutral': neutral,
                'accuracy_pct': round(accuracy, 1),
                'avg_change_1d': round(avg_change, 2),
                'total_adjustments': adjustments,
                'current_weights': weights,
            }
        finally:
            conn.close()

    def get_history(self, limit: int = 50) -> List[dict]:
        """Retorna las últimas recomendaciones verificadas."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT ticker, scan_date, score, viability, price_at_rec,
                       price_next_day, change_pct_1d, change_pct_3d, change_pct_7d,
                       outcome, user_feedback, sector, rsi, verified
                FROM recommendations
                ORDER BY scan_date DESC, score DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_sector_stats(self) -> List[dict]:
        """Estadísticas por sector."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT sector,
                       COUNT(*) as total,
                       SUM(CASE WHEN outcome IN ('good_mild','good_strong') THEN 1 ELSE 0 END) as good,
                       SUM(CASE WHEN outcome IN ('bad_mild','bad_severe') THEN 1 ELSE 0 END) as bad,
                       AVG(change_pct_1d) as avg_change
                FROM recommendations
                WHERE verified=1 AND sector IS NOT NULL AND sector != 'N/A'
                GROUP BY sector
                ORDER BY avg_change DESC
            """).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_confidence_for_ticker(self, ticker: str, sector: str = '',
                                   rsi: float = 50) -> dict:
        """
        Calcula un score de confianza para un ticker basado en
        el historial de tickers similares.
        """
        conn = self._get_conn()
        try:
            # 1. Historial directo del ticker
            direct = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN outcome IN ('good_mild','good_strong') THEN 1 ELSE 0 END) as good,
                       SUM(CASE WHEN outcome IN ('bad_mild','bad_severe') THEN 1 ELSE 0 END) as bad,
                       AVG(change_pct_1d) as avg_change
                FROM recommendations WHERE ticker=? AND verified=1
            """, (ticker,)).fetchone()

            # 2. Historial del sector
            sector_data = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN outcome IN ('good_mild','good_strong') THEN 1 ELSE 0 END) as good,
                       AVG(change_pct_1d) as avg_change
                FROM recommendations WHERE sector=? AND verified=1
            """, (sector,)).fetchone() if sector else None

            # 3. Historial de tickers con RSI similar (±10)
            rsi_similar = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN outcome IN ('good_mild','good_strong') THEN 1 ELSE 0 END) as good,
                       AVG(change_pct_1d) as avg_change
                FROM recommendations
                WHERE verified=1 AND rsi BETWEEN ? AND ?
            """, (rsi - 10, rsi + 10)).fetchone()

            # Calcular confianza compuesta
            confidence = 50.0  # Base neutral
            notes = []

            if direct and direct['total'] > 0:
                direct_rate = (direct['good'] / direct['total']) * 100
                # Peso alto para datos directos
                confidence = confidence * 0.4 + direct_rate * 0.6
                if direct['bad'] > direct['good']:
                    notes.append(f"⚠️ {ticker} ha fallado {direct['bad']}/{direct['total']} veces")
                elif direct['good'] > 0:
                    notes.append(f"✅ {ticker} acertó {direct['good']}/{direct['total']} veces")

            if sector_data and sector_data['total'] > 3:
                sector_rate = (sector_data['good'] / sector_data['total']) * 100
                confidence = confidence * 0.7 + sector_rate * 0.3
                if sector_data['avg_change'] and sector_data['avg_change'] < -5:
                    notes.append(f"⚠️ Sector '{sector}' con tendencia negativa")

            if rsi_similar and rsi_similar['total'] > 5:
                rsi_rate = (rsi_similar['good'] / rsi_similar['total']) * 100
                if rsi_rate < 30:
                    confidence *= 0.8
                    notes.append(f"⚠️ RSI ~{rsi:.0f} ha tenido baja precisión")

            # Bonus/penalización por user feedback negativo
            user_bad = conn.execute("""
                SELECT COUNT(*) c FROM recommendations
                WHERE ticker=? AND user_feedback='bad'
            """, (ticker,)).fetchone()['c']
            if user_bad > 0:
                confidence *= 0.7
                notes.append(f"👎 {user_bad} feedback(s) negativos del usuario")

            confidence = max(5, min(99, confidence))

            level = 'alta' if confidence >= 70 else 'media' if confidence >= 40 else 'baja'

            return {
                'confidence': round(confidence, 1),
                'level': level,
                'notes': notes,
                'direct_history': direct['total'] if direct else 0,
            }
        finally:
            conn.close()

    def record_live_alert(self, ticker: str, price: float, signal_type: str, reason: str, confidence: float):
        """Registra una alerta enviada en vivo en la base de datos."""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO live_alerts (ticker, price, signal_type, trigger_reason, ai_confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (ticker, price, signal_type, reason, confidence))
            conn.commit()
        except Exception as e:
            logger.error(f"Error registrando alerta en vivo para {ticker}: {e}")
        finally:
            conn.close()

    def has_recent_alert(self, ticker: str, signal_type: str, hours: float = 4.0) -> bool:
        """Verifica si ya se envió una alerta reciente del mismo tipo para este ticker."""
        conn = self._get_conn()
        try:
            time_modifier = f"-{int(hours * 60)} minutes"
            cursor = conn.execute("""
                SELECT COUNT(*) c FROM live_alerts
                WHERE ticker=? AND signal_type=? 
                  AND sent_at >= datetime('now', ?)
            """, (ticker, signal_type, time_modifier))
            return cursor.fetchone()['c'] > 0
        except Exception as e:
            logger.error(f"Error comprobando alerta reciente para {ticker}: {e}")
            return False
        finally:
            conn.close()

    def get_live_alerts_history(self, limit: int = 50) -> List[dict]:
        """Retorna las últimas alertas enviadas en vivo."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT id, ticker, price, signal_type, trigger_reason, ai_confidence, sent_at
                FROM live_alerts
                ORDER BY sent_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error cargando historial de alertas en vivo: {e}")
            return []
        finally:
            conn.close()


# ── Motor de aprendizaje ─────────────────────────────────────────────────────

class AdaptiveLearner:
    """
    Motor principal que coordina el registro de recomendaciones,
    la verificación de resultados, y el ajuste de pesos.
    """

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db = RecommendationDB(db_path)
        self._last_decay = None
        logger.info("🧠 AdaptiveLearner inicializado.")

    def get_adaptive_weights(self) -> Dict[str, float]:
        """Retorna los pesos adaptativos actuales."""
        return self.db.get_weights()

    def record_scan_results(self, results: list, top_n: int = 50):
        """
        Registra las top N recomendaciones de un escaneo.
        Se llama después de cada escaneo exitoso.
        """
        if not results:
            return

        sorted_results = sorted(results, key=lambda x: x.get('Score', 0), reverse=True)
        recorded = 0

        for r in sorted_results[:top_n]:
            ticker = r.get('Ticker', '')
            if not ticker:
                continue

            score = r.get('Score', 0)
            price = r.get('Price', 0)
            if price <= 0:
                continue

            # Determinar qué indicadores contribuyeron al score
            active = self._identify_active_indicators(r)

            indicators = {
                'rsi': r.get('RSI'),
                'macd': r.get('MACD'),
                'macd_signal': r.get('MACD_Signal'),
                'macd_hist': r.get('MACD_Hist'),
                'bb_upper': r.get('BB_Upper'),
                'bb_lower': r.get('BB_Lower'),
                'vol_ratio': r.get('Vol_Ratio'),
                'volatility_pct': r.get('Volatility_Percent'),
                'market_cap': r.get('Market_Cap'),
                'sector': r.get('Sector', 'N/A'),
            }

            rec_id = self.db.record_recommendation(
                ticker=ticker, score=score, price=price,
                indicators=indicators, active_indicators=active,
                viability=r.get('Viabilidad', '')
            )
            if rec_id > 0:
                recorded += 1

        logger.info(f"🧠 Registradas {recorded} recomendaciones del escaneo.")

    def verify_past_recommendations(self):
        """
        Verifica recomendaciones pasadas descargando precios actualizados.
        Se ejecuta al inicio de cada escaneo.
        """
        from stock_scanner import _fetch_history_raw

        pending = self.db.get_pending_verifications(min_age_days=1)
        if not pending:
            logger.info("🧠 Sin recomendaciones pendientes de verificación.")
            return

        logger.info(f"🧠 Verificando {len(pending)} recomendaciones pasadas...")
        verified_count = 0
        adjustments = 0

        for rec in pending:
            ticker = rec['ticker']
            scan_date = rec['scan_date']
            price_at_rec = rec['price_at_rec']

            if not price_at_rec or price_at_rec <= 0:
                continue

            try:
                # Descargar precios recientes
                df = _fetch_history_raw(ticker, period='1mo')
                if df is None or df.empty:
                    continue

                scan_dt = datetime.strptime(scan_date, '%Y-%m-%d')

                # Buscar precio a 1 día
                price_1d = self._find_price_on_date(df, scan_dt + timedelta(days=1))
                # Buscar precio a 3 días
                price_3d = self._find_price_on_date(df, scan_dt + timedelta(days=3))
                # Buscar precio a 7 días
                price_7d = self._find_price_on_date(df, scan_dt + timedelta(days=7))

                if price_1d is None:
                    # Intentar día hábil siguiente
                    for offset in range(2, 5):
                        price_1d = self._find_price_on_date(df, scan_dt + timedelta(days=offset))
                        if price_1d:
                            break

                if price_1d is None:
                    continue  # Aún no hay datos

                outcome, change_pct = self.db.update_verification(
                    rec['id'], price_1d, price_3d, price_7d, price_at_rec
                )

                verified_count += 1

                # Ajustar pesos según resultado
                active_indicators = json.loads(rec.get('active_indicators', '[]') or '[]')
                adj = self._process_outcome(
                    outcome, change_pct, ticker, active_indicators
                )
                adjustments += adj

            except Exception as e:
                logger.debug(f"Error verificando {ticker}: {e}")

        # Aplicar decay semanal si hace falta
        self._maybe_apply_decay()

        logger.info(
            f"🧠 Verificación completada: {verified_count} verificadas, "
            f"{adjustments} ajustes de pesos realizados."
        )

    def get_confidence(self, ticker: str, sector: str = '', rsi: float = 50) -> dict:
        """Obtiene el score de confianza para un ticker."""
        return self.db.get_confidence_for_ticker(ticker, sector, rsi)

    def get_stats(self) -> dict:
        """Retorna estadísticas del learner."""
        return self.db.get_stats()

    def get_history(self, limit: int = 50) -> list:
        """Retorna historial de recomendaciones."""
        return self.db.get_history(limit)

    def submit_user_feedback(self, ticker: str, feedback: str = 'bad'):
        """Procesa feedback manual del usuario."""
        self.db.record_user_feedback(ticker=ticker, feedback=feedback)

        if feedback == 'bad':
            # Aplicar penalización extra
            conn = self.db._get_conn()
            try:
                rec = conn.execute("""
                    SELECT * FROM recommendations
                    WHERE ticker=? ORDER BY scan_date DESC LIMIT 1
                """, (ticker,)).fetchone()
                if rec:
                    active = json.loads(rec['active_indicators'] or '[]')
                    for ind in active:
                        self.db.adjust_weight(
                            ind, PENALTY_FACTOR_MILD,
                            'user_feedback_bad', ticker, 0
                        )
            finally:
                conn.close()

        logger.info(f"🧠 Feedback del usuario registrado: {ticker} → {feedback}")

    def record_live_alert(self, ticker: str, price: float, signal_type: str, reason: str, confidence: float):
        self.db.record_live_alert(ticker, price, signal_type, reason, confidence)

    def has_recent_alert(self, ticker: str, signal_type: str, hours: float = 4.0) -> bool:
        return self.db.has_recent_alert(ticker, signal_type, hours)

    def get_live_alerts_history(self, limit: int = 50) -> list:
        return self.db.get_live_alerts_history(limit)

    # ── Internos ───────────────────────────────────────────────────────────────

    def _identify_active_indicators(self, result: dict) -> list:
        """Identifica qué indicadores contribuyeron positivamente al score."""
        active = []
        rsi = result.get('RSI', 50)
        price = result.get('Price', 0)
        ma100 = result.get('MA100', 0)
        ma200 = result.get('MA200', 0)
        macd = result.get('MACD', 0)
        macd_sig = result.get('MACD_Signal', 0)
        macd_hist = result.get('MACD_Hist', 0)
        bb_lower = result.get('BB_Lower', 0)
        bb_upper = result.get('BB_Upper', 0)
        vol_ratio = result.get('Vol_Ratio', 0)
        avg_vol = result.get('Avg_Volume', 0)
        market_cap = result.get('Market_Cap', 0)

        if 40 <= rsi <= 60:
            active.append('rsi_optimal')
        elif rsi < 30:
            active.append('rsi_extreme_low')

        if price > ma100 > ma200 and ma200 > 0:
            active.append('trend_sma')

        if macd > macd_sig and macd_hist > 0:
            active.append('macd_bullish')

        if avg_vol > 2_000_000:
            active.append('volume_high')

        if vol_ratio > 1.5:
            active.append('volume_ratio')

        if market_cap > 10e9:
            active.append('market_cap_large')

        if bb_lower > 0 and price <= bb_lower:
            active.append('bb_oversold')

        if bb_upper > 0 and price >= bb_upper:
            active.append('bb_overbought')

        return active

    def _find_price_on_date(self, df, target_date) -> Optional[float]:
        """Busca el precio de cierre en o cerca de una fecha específica."""
        try:
            target_str = target_date.strftime('%Y-%m-%d')
            # Buscar exacta
            mask = df.index.strftime('%Y-%m-%d') == target_str
            if mask.any():
                return float(df.loc[mask, 'Close'].iloc[0])

            # Buscar el día más cercano posterior
            future = df[df.index >= target_date.strftime('%Y-%m-%d')]
            if not future.empty:
                return float(future['Close'].iloc[0])

            return None
        except Exception:
            return None

    def _process_outcome(self, outcome: str, change_pct: float,
                          ticker: str, active_indicators: list) -> int:
        """Procesa el resultado y ajusta pesos según corresponda."""
        if not active_indicators:
            return 0

        adjustments = 0

        if outcome == 'bad_severe':
            # Penalización fuerte: la acción cayó ≥15%
            for ind in active_indicators:
                self.db.adjust_weight(
                    ind, PENALTY_FACTOR_SEVERE,
                    'penalty_severe', ticker, change_pct
                )
                adjustments += 1
            logger.warning(
                f"🔴 {ticker}: cayó {change_pct:.1f}% — penalizados {len(active_indicators)} indicadores"
            )

        elif outcome == 'bad_mild':
            # Penalización leve: caída 5-15%
            for ind in active_indicators:
                self.db.adjust_weight(
                    ind, PENALTY_FACTOR_MILD,
                    'penalty_mild', ticker, change_pct
                )
                adjustments += 1
            logger.warning(
                f"🟠 {ticker}: cayó {change_pct:.1f}% — penalización leve"
            )

        elif outcome == 'good_strong':
            # Recompensa fuerte: subió ≥5%
            for ind in active_indicators:
                self.db.adjust_weight(
                    ind, REWARD_FACTOR_STRONG,
                    'reward_strong', ticker, change_pct
                )
                adjustments += 1
            logger.info(
                f"🟢 {ticker}: subió {change_pct:.1f}% — recompensados {len(active_indicators)} indicadores"
            )

        elif outcome == 'good_mild':
            # Recompensa leve: subió 2-5%
            for ind in active_indicators:
                self.db.adjust_weight(
                    ind, REWARD_FACTOR_MILD,
                    'reward_mild', ticker, change_pct
                )
                adjustments += 1

        return adjustments

    def _maybe_apply_decay(self):
        """Aplica decay semanal si no se ha hecho esta semana."""
        now = datetime.now()
        if self._last_decay and (now - self._last_decay).days < 7:
            return
        self.db.apply_weekly_decay()
        self._last_decay = now
        logger.info("🧠 Decay semanal aplicado a pesos adaptativos.")


# ── Singleton global ──────────────────────────────────────────────────────────
_learner_instance: Optional[AdaptiveLearner] = None


def get_learner() -> AdaptiveLearner:
    """Obtiene o crea la instancia singleton del learner."""
    global _learner_instance
    if _learner_instance is None:
        _learner_instance = AdaptiveLearner()
    return _learner_instance
