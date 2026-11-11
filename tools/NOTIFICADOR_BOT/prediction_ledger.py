"""Registro inmutable y verificación temporal de predicciones bursátiles."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd


HORIZONS = (1, 3, 5, 10, 20)
FEEDBACK_VALUES = {"positive", "negative"}
FEEDBACK_REASONS = {
    "signal_quality",
    "timing",
    "risk_level",
    "data_quality",
    "explanation",
    "other",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return json_safe(value.item())
    return value


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    return current + timedelta(days=(weekday - current.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """Algoritmo gregoriano de Meeus/Jones/Butcher."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


class NyseCalendar:
    """Calendario NYSE reproducible para sesiones, cierres y medias sesiones."""

    timezone = ZoneInfo("America/New_York")

    def holidays(self, year: int) -> set[date]:
        holidays = {
            _observed(date(year, 1, 1)),
            _nth_weekday(year, 1, 0, 3),
            _nth_weekday(year, 2, 0, 3),
            _easter(year) - timedelta(days=2),
            _last_weekday(year, 5, 0),
            _observed(date(year, 7, 4)),
            _nth_weekday(year, 9, 0, 1),
            _nth_weekday(year, 11, 3, 4),
            _observed(date(year, 12, 25)),
        }
        if year >= 2022:
            holidays.add(_observed(date(year, 6, 19)))
        if year == 2025:
            # NYSE: cierre extraordinario nacional (Jimmy Carter).
            holidays.add(date(2025, 1, 9))
        next_new_year_observed = _observed(date(year + 1, 1, 1))
        if next_new_year_observed.year == year:
            holidays.add(next_new_year_observed)
        return holidays

    def is_session(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays(day.year)

    def is_half_session(self, day: date) -> bool:
        thanksgiving = _nth_weekday(day.year, 11, 3, 4)
        day_after_thanksgiving = thanksgiving + timedelta(days=1)
        christmas_eve = date(day.year, 12, 24)
        july_third = date(day.year, 7, 3)
        return self.is_session(day) and day in {day_after_thanksgiving, christmas_eve, july_third}

    def close_time(self, day: date) -> datetime:
        closing = time(13, 0) if self.is_half_session(day) else time(16, 0)
        return datetime.combine(day, closing, self.timezone).astimezone(timezone.utc)

    def next_session(self, after: date) -> date:
        candidate = after + timedelta(days=1)
        while not self.is_session(candidate):
            candidate += timedelta(days=1)
        return candidate

    def advance_sessions(self, start: date, count: int) -> date:
        result = start
        for _ in range(count):
            result = self.next_session(result)
        return result


@dataclass(frozen=True)
class CostPolicy:
    commission_entry_bps: float = 0.0
    commission_exit_bps: float = 0.0
    spread_bps: float = 5.0
    slippage_bps: float = 5.0

    @property
    def total_rate(self) -> float:
        return (
            self.commission_entry_bps
            + self.commission_exit_bps
            + self.spread_bps
            + self.slippage_bps
        ) / 10_000


class PredictionLedger:
    """SQLite append-only para predicciones, resultados y feedback."""

    def __init__(self, db_path: str | Path, calendar: NyseCalendar | None = None):
        self.db_path = str(db_path)
        self.calendar = calendar or NyseCalendar()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS predictions_v3 (
                    prediction_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    market TEXT NOT NULL,
                    data_timestamp TEXT NOT NULL,
                    emitted_at TEXT NOT NULL,
                    horizon_sessions INTEGER NOT NULL CHECK(horizon_sessions IN (1,3,5,10,20)),
                    expected_entry_session TEXT NOT NULL,
                    expected_entry_policy TEXT NOT NULL,
                    expected_entry_price REAL,
                    features_json TEXT NOT NULL,
                    feature_version TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    probability REAL,
                    score REAL NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    model_hash TEXT NOT NULL,
                    risk_rules_json TEXT NOT NULL,
                    data_provider TEXT NOT NULL,
                    quote_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prediction_results_v3 (
                    prediction_id TEXT PRIMARY KEY REFERENCES predictions_v3(prediction_id),
                    horizon_sessions INTEGER NOT NULL CHECK(horizon_sessions IN (1,3,5,10,20)),
                    due_session TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PENDING','VERIFIED','IRRECOVERABLE')),
                    entry_session TEXT,
                    exit_session TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    gross_return REAL,
                    commission_entry REAL,
                    commission_exit REAL,
                    spread_cost REAL,
                    slippage_cost REAL,
                    total_cost REAL,
                    net_return REAL,
                    positive_threshold REAL,
                    negative_threshold REAL,
                    market_label TEXT,
                    opportunity_cost REAL,
                    verified_at TEXT,
                    resolution_reason TEXT,
                    UNIQUE(prediction_id, horizon_sessions)
                );
                CREATE TABLE IF NOT EXISTS prediction_feedback_v3 (
                    feedback_id TEXT PRIMARY KEY,
                    prediction_id TEXT NOT NULL REFERENCES predictions_v3(prediction_id),
                    symbol TEXT NOT NULL,
                    feedback TEXT NOT NULL CHECK(feedback IN ('positive','negative')),
                    reason TEXT NOT NULL,
                    note TEXT,
                    user_id TEXT NOT NULL,
                    user_role TEXT NOT NULL,
                    submitted_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_adjustment_audit_v3 (
                    adjustment_id TEXT PRIMARY KEY,
                    proposed_at TEXT NOT NULL,
                    proposed_by TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    old_version TEXT NOT NULL,
                    proposed_version TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PROPOSED','REJECTED','APPROVED','APPLIED')),
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    reason TEXT
                );
                CREATE TABLE IF NOT EXISTS legacy_recovery_v3 (
                    legacy_source TEXT NOT NULL,
                    legacy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    scan_date TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('MIGRATED','IRRECOVERABLE')),
                    reason TEXT NOT NULL,
                    resolved_at TEXT NOT NULL,
                    PRIMARY KEY(legacy_source, legacy_id)
                );
                CREATE INDEX IF NOT EXISTS idx_prediction_due_v3 ON prediction_results_v3(status, due_session);
                CREATE INDEX IF NOT EXISTS idx_prediction_symbol_v3 ON predictions_v3(symbol, emitted_at);
                CREATE TRIGGER IF NOT EXISTS predictions_v3_no_update
                    BEFORE UPDATE ON predictions_v3 BEGIN SELECT RAISE(ABORT, 'predictions_v3 is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS predictions_v3_no_delete
                    BEFORE DELETE ON predictions_v3 BEGIN SELECT RAISE(ABORT, 'predictions_v3 is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS feedback_v3_no_update
                    BEFORE UPDATE ON prediction_feedback_v3 BEGIN SELECT RAISE(ABORT, 'prediction_feedback_v3 is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS feedback_v3_no_delete
                    BEFORE DELETE ON prediction_feedback_v3 BEGIN SELECT RAISE(ABORT, 'prediction_feedback_v3 is immutable'); END;
            """)

    def record_prediction(self, payload: Mapping[str, Any]) -> str:
        horizon = int(payload["horizon_sessions"])
        if horizon not in HORIZONS:
            raise ValueError(f"Horizonte no soportado: {horizon}")
        data_timestamp = parse_timestamp(payload["data_timestamp"])
        emitted_at = parse_timestamp(payload.get("emitted_at") or utc_now())
        entry_session = self.calendar.next_session(data_timestamp.astimezone(self.calendar.timezone).date())
        due_session = self.calendar.advance_sessions(entry_session, horizon - 1)
        prediction_id = str(payload.get("prediction_id") or uuid.uuid4())
        features_json = json.dumps(json_safe(payload["features"]), sort_keys=True, separators=(",", ":"), allow_nan=False)
        risk_json = json.dumps(json_safe(payload.get("risk_rules", {})), sort_keys=True, separators=(",", ":"), allow_nan=False)
        quote_json = json.dumps(json_safe(payload["quote"]), sort_keys=True, separators=(",", ":"), allow_nan=False)
        values = (
            prediction_id,
            str(payload["symbol"]).upper(),
            payload.get("market", "XNYS"),
            iso_utc(data_timestamp),
            iso_utc(emitted_at),
            horizon,
            entry_session.isoformat(),
            "NEXT_SESSION_OPEN",
            payload.get("expected_entry_price"),
            features_json,
            payload["feature_version"],
            payload["signal"],
            payload.get("probability"),
            float(payload["score"]),
            payload.get("model_name", "heuristic"),
            payload["model_version"],
            payload.get("model_hash") or hashlib.sha256(payload["model_version"].encode()).hexdigest(),
            risk_json,
            payload["data_provider"],
            quote_json,
            iso_utc(utc_now()),
        )
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO predictions_v3 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, values)
            connection.execute("""
                INSERT INTO prediction_results_v3
                    (prediction_id, horizon_sessions, due_session, status)
                VALUES (?, ?, ?, 'PENDING')
            """, (prediction_id, horizon, due_session.isoformat()))
        return prediction_id

    def record_scan_results(self, results: Iterable[Mapping[str, Any]], top_n: int = 50) -> list[str]:
        recorded: list[str] = []
        eligible = [row for row in results if row.get("Signal_Eligible") is True]
        for row in sorted(eligible, key=lambda item: item.get("Score", 0), reverse=True)[:top_n]:
            quote = row.get("Quote") or {}
            if not quote.get("market_timestamp") or not quote.get("provider"):
                continue
            horizon_map = row.get("Horizon_Scores") or {}
            row_prediction_ids: dict[str, str] = {}
            for horizon in HORIZONS:
                group = "short" if horizon in (1, 3) else "swing" if horizon in (5, 10) else "trend"
                horizon_result = horizon_map.get(group) or {}
                signal = horizon_result.get("state", row.get("Signal_State", "SIN SEÑAL"))
                if signal == "SIN SEÑAL":
                    continue
                probability = row.get("Calibrated_Probability")
                prediction_id = self.record_prediction({
                    "symbol": row["Ticker"],
                    "market": "XNYS",
                    "data_timestamp": quote["market_timestamp"],
                    "emitted_at": quote.get("received_at") or utc_now(),
                    "horizon_sessions": horizon,
                    "expected_entry_price": quote.get("price"),
                    "features": {
                        "rsi": row.get("RSI"),
                        "macd": row.get("MACD"),
                        "macd_signal": row.get("MACD_Signal"),
                        "macd_histogram": row.get("MACD_Hist"),
                        "macd_histogram_slope": row.get("MACD_Hist_Slope"),
                        "bb_upper": row.get("BB_Upper"),
                        "bb_lower": row.get("BB_Lower"),
                        "atr": row.get("ATR"),
                        "volume_ratio": row.get("Vol_Ratio"),
                        "market_cap": row.get("Market_Cap"),
                        "horizon": horizon_result,
                    },
                    "feature_version": row.get("Heuristic_Version", "unknown"),
                    "signal": signal,
                    "probability": probability,
                    "score": horizon_result.get("score", row.get("Score", 0)),
                    "model_name": row.get("ML_Source", "heuristic"),
                    "model_version": row.get("Model_Version") or row.get("Heuristic_Version", "unknown"),
                    "model_hash": row.get("Model_Hash"),
                    "risk_rules": {
                        "signal_restrictions": row.get("Signal_Restrictions", []),
                        "data_quality_minimum": 0.90,
                    },
                    "data_provider": quote["provider"],
                    "quote": quote,
                })
                recorded.append(prediction_id)
                row_prediction_ids[str(horizon)] = prediction_id
            if isinstance(row, dict):
                row["Prediction_IDs"] = row_prediction_ids
        return recorded

    def get_prediction(self, prediction_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM predictions_v3 WHERE prediction_id=?", (prediction_id,)).fetchone()
            return dict(row) if row else None

    def pending_due(self, as_of: datetime | None = None) -> list[dict[str, Any]]:
        current = (as_of or utc_now()).astimezone(self.calendar.timezone)
        with self._connection() as connection:
            rows = connection.execute("""
                SELECT p.*, r.due_session, r.status
                FROM predictions_v3 p JOIN prediction_results_v3 r USING(prediction_id)
                WHERE r.status='PENDING' AND r.due_session <= ?
                ORDER BY r.due_session, p.prediction_id
            """, (current.date().isoformat(),)).fetchall()
            return [dict(row) for row in rows]

    def verify(self, prediction_id: str, history: pd.DataFrame, costs: CostPolicy | None = None,
               as_of: datetime | None = None) -> dict[str, Any]:
        costs = costs or CostPolicy()
        prediction = self.get_prediction(prediction_id)
        if not prediction:
            raise KeyError(prediction_id)
        with self._connection() as connection:
            result = connection.execute(
                "SELECT * FROM prediction_results_v3 WHERE prediction_id=?", (prediction_id,)
            ).fetchone()
        if result["status"] != "PENDING":
            return dict(result)
        if history is None or history.empty:
            raise ValueError("Sin histórico para verificar")
        frame = history.copy()
        index = pd.DatetimeIndex(frame.index)
        if index.tz is None:
            index = index.tz_localize("UTC")
        local_dates = index.tz_convert(self.calendar.timezone).date
        frame = frame.assign(_session=local_dates).drop_duplicates("_session", keep="last").set_index("_session")
        entry_session = date.fromisoformat(prediction["expected_entry_session"])
        due_session = date.fromisoformat(result["due_session"])
        if entry_session not in frame.index or due_session not in frame.index:
            raise ValueError("Histórico incompleto para las sesiones de entrada/salida")
        current = as_of or utc_now()
        if current < self.calendar.close_time(due_session):
            raise ValueError("El horizonte aún no ha vencido")
        entry_price = float(frame.loc[entry_session, "Open"])
        exit_price = float(frame.loc[due_session, "Close"])
        if entry_price <= 0 or exit_price <= 0:
            raise ValueError("Precio de ejecución inválido")
        gross_return = exit_price / entry_price - 1
        entry_commission = costs.commission_entry_bps / 10_000
        exit_commission = costs.commission_exit_bps / 10_000
        spread = costs.spread_bps / 10_000
        slippage = costs.slippage_bps / 10_000
        total_cost = costs.total_rate
        net_return = gross_return - total_cost
        features = json.loads(prediction["features_json"])
        volatility = abs(float(features.get("atr") or 0) / entry_price)
        threshold = max(0.005, volatility * (prediction["horizon_sessions"] ** 0.5) * 0.50)
        signal = prediction["signal"]
        if signal == "COMPRAR":
            label = "COMPRA_EXITOSA" if net_return >= threshold else "COMPRA_FALLIDA" if net_return <= -threshold else "NEUTRAL"
            opportunity_cost = None
        elif signal in {"REDUCIR", "SALIR"}:
            label = "SALIDA_CORRECTA" if net_return <= -threshold else "SALIDA_INCORRECTA" if net_return >= threshold else "NEUTRAL"
            opportunity_cost = net_return
        else:
            label = "NEUTRAL"
            opportunity_cost = None
        verified_at = iso_utc(current)
        with self._connection() as connection:
            connection.execute("""
                UPDATE prediction_results_v3 SET
                    status='VERIFIED', entry_session=?, exit_session=?, entry_price=?, exit_price=?,
                    gross_return=?, commission_entry=?, commission_exit=?, spread_cost=?,
                    slippage_cost=?, total_cost=?, net_return=?, positive_threshold=?,
                    negative_threshold=?, market_label=?, opportunity_cost=?, verified_at=?,
                    resolution_reason='AUTOMATIC_MARKET_VERIFICATION'
                WHERE prediction_id=? AND status='PENDING'
            """, (
                entry_session.isoformat(), due_session.isoformat(), entry_price, exit_price,
                gross_return, entry_commission, exit_commission, spread, slippage, total_cost,
                net_return, threshold, -threshold, label, opportunity_cost, verified_at, prediction_id,
            ))
            row = connection.execute(
                "SELECT * FROM prediction_results_v3 WHERE prediction_id=?", (prediction_id,)
            ).fetchone()
            return dict(row)

    def verify_due(self, history_provider: Callable[[str, date, date], pd.DataFrame | None],
                   costs: CostPolicy | None = None, as_of: datetime | None = None,
                   grace_sessions: int = 1) -> dict[str, int]:
        current = as_of or utc_now()
        summary = {"verified": 0, "pending": 0, "irrecoverable": 0}
        for prediction in self.pending_due(current):
            entry = date.fromisoformat(prediction["expected_entry_session"])
            due = date.fromisoformat(prediction["due_session"])
            try:
                history = history_provider(prediction["symbol"], entry, due)
                self.verify(prediction["prediction_id"], history, costs, current)
                summary["verified"] += 1
            except Exception as error:
                expiry = self.calendar.advance_sessions(due, grace_sessions)
                if current.astimezone(self.calendar.timezone).date() > expiry:
                    self.mark_irrecoverable(
                        prediction["prediction_id"],
                        f"NO_MARKET_DATA_AFTER_GRACE: possible suspension/delisting; {error}",
                        current,
                    )
                    summary["irrecoverable"] += 1
                else:
                    summary["pending"] += 1
        return summary

    def mark_irrecoverable(self, prediction_id: str, reason: str, when: datetime | None = None) -> None:
        if not reason.strip():
            raise ValueError("Una resolución irrecuperable requiere motivo")
        with self._connection() as connection:
            connection.execute("""
                UPDATE prediction_results_v3
                SET status='IRRECOVERABLE', verified_at=?, resolution_reason=?
                WHERE prediction_id=? AND status='PENDING'
            """, (iso_utc(when or utc_now()), reason.strip(), prediction_id))

    def record_feedback(self, prediction_id: str, feedback: str, reason: str,
                        user_id: str, user_role: str, note: str = "",
                        submitted_at: datetime | None = None) -> str:
        if feedback not in FEEDBACK_VALUES:
            raise ValueError("Feedback debe ser positive o negative")
        if reason not in FEEDBACK_REASONS:
            raise ValueError("Motivo de feedback no soportado")
        prediction = self.get_prediction(prediction_id)
        if not prediction:
            raise KeyError(prediction_id)
        if not user_id.strip() or not user_role.strip():
            raise ValueError("Feedback requiere usuario y rol")
        feedback_id = str(uuid.uuid4())
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO prediction_feedback_v3
                    (feedback_id,prediction_id,symbol,feedback,reason,note,user_id,user_role,submitted_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                feedback_id, prediction_id, prediction["symbol"], feedback, reason, note,
                user_id.strip(), user_role.strip(), iso_utc(submitted_at or utc_now()),
            ))
        return feedback_id

    def propose_adjustment(self, proposed_by: str, evidence: Mapping[str, Any],
                           old_version: str, proposed_version: str, reason: str) -> str:
        """Registra una propuesta; no cambia ningún modelo ni peso activo."""
        if not all(value.strip() for value in (proposed_by, old_version, proposed_version, reason)):
            raise ValueError("La propuesta requiere autor, versiones y motivo")
        adjustment_id = str(uuid.uuid4())
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO model_adjustment_audit_v3
                    (adjustment_id,proposed_at,proposed_by,evidence_json,old_version,
                     proposed_version,status,reason)
                VALUES (?,?,?,?,?,?,'PROPOSED',?)
            """, (
                adjustment_id, iso_utc(utc_now()), proposed_by,
                json.dumps(json_safe(evidence), sort_keys=True, allow_nan=False),
                old_version, proposed_version, reason,
            ))
        return adjustment_id

    def review_adjustment(self, adjustment_id: str, approved: bool,
                          reviewed_by: str, reason: str) -> None:
        if not reviewed_by.strip() or not reason.strip():
            raise ValueError("La revisión requiere revisor y motivo")
        status = "APPROVED" if approved else "REJECTED"
        with self._connection() as connection:
            cursor = connection.execute("""
                UPDATE model_adjustment_audit_v3
                SET status=?,reviewed_by=?,reviewed_at=?,reason=?
                WHERE adjustment_id=? AND status='PROPOSED'
            """, (status, reviewed_by, iso_utc(utc_now()), reason, adjustment_id))
            if cursor.rowcount != 1:
                raise ValueError("Ajuste inexistente o ya revisado")

    def unresolved_count(self) -> int:
        with self._connection() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM prediction_results_v3 WHERE status='PENDING'"
            ).fetchone()[0]

    def get_stats(self) -> dict[str, Any]:
        with self._connection() as connection:
            total = connection.execute("SELECT COUNT(*) FROM predictions_v3").fetchone()[0]
            verified = connection.execute(
                "SELECT COUNT(*) FROM prediction_results_v3 WHERE status='VERIFIED'"
            ).fetchone()[0]
            successful = connection.execute("""
                SELECT COUNT(*) FROM prediction_results_v3
                WHERE status='VERIFIED' AND market_label IN ('COMPRA_EXITOSA','SALIDA_CORRECTA')
            """).fetchone()[0]
            average = connection.execute("""
                SELECT AVG(net_return) FROM prediction_results_v3 WHERE status='VERIFIED'
            """).fetchone()[0]
            adjustments = connection.execute("""
                SELECT COUNT(*) FROM model_adjustment_audit_v3 WHERE status='APPLIED'
            """).fetchone()[0]
            pending = connection.execute(
                "SELECT COUNT(*) FROM prediction_results_v3 WHERE status='PENDING'"
            ).fetchone()[0]
            irrecoverable = connection.execute(
                "SELECT COUNT(*) FROM prediction_results_v3 WHERE status='IRRECOVERABLE'"
            ).fetchone()[0]
            legacy_irrecoverable = connection.execute(
                "SELECT COUNT(*) FROM legacy_recovery_v3 WHERE status='IRRECOVERABLE'"
            ).fetchone()[0]
        return {
            "total_recommendations": total,
            "verified": verified,
            "successful_outcomes": successful,
            "accuracy_pct": round(successful / verified * 100, 1) if verified else None,
            "avg_change_1d": round((average or 0) * 100, 2) if verified else None,
            "total_adjustments": adjustments,
            "pending": pending,
            "irrecoverable": irrecoverable,
            "legacy_irrecoverable": legacy_irrecoverable,
        }

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("""
                SELECT p.prediction_id,p.emitted_at,p.symbol,p.score,p.expected_entry_price,
                       p.horizon_sessions,p.signal,p.model_version,r.status,r.net_return,
                       r.market_label,r.resolution_reason
                FROM predictions_v3 p JOIN prediction_results_v3 r USING(prediction_id)
                ORDER BY p.emitted_at DESC, p.prediction_id DESC LIMIT ?
            """, (max(1, min(int(limit), 500)),)).fetchall()
        return [{
            "prediction_id": row["prediction_id"],
            "scan_date": row["emitted_at"],
            "ticker": row["symbol"],
            "score": row["score"],
            "price_at_rec": row["expected_entry_price"],
            "horizon_sessions": row["horizon_sessions"],
            "signal": row["signal"],
            "model_version": row["model_version"],
            "status": row["status"],
            "change_pct_1d": row["net_return"] * 100 if row["net_return"] is not None else None,
            "outcome": row["market_label"],
            "resolution_reason": row["resolution_reason"],
        } for row in rows]

    def import_legacy_as_irrecoverable(self, legacy_path: str | Path, source: str = "learner_v1") -> list[dict[str, Any]]:
        uri = f"file:{Path(legacy_path).resolve()}?mode=ro&immutable=1"
        legacy = sqlite3.connect(uri, uri=True)
        legacy.row_factory = sqlite3.Row
        rows = legacy.execute("""
            SELECT id,ticker,scan_date,created_at FROM recommendations
            WHERE verified=0
        """).fetchall()
        legacy.close()
        reason = (
            "IRRECOVERABLE_LEGACY_SCHEMA: falta timestamp UTC de datos/emisión, horizonte, "
            "entrada t+1, fuente, versiones/hash y reglas de costos; no es posible reconstruir "
            "una etiqueta sin introducir supuestos o fuga temporal"
        )
        resolved_at = iso_utc(utc_now())
        with self._connection() as connection:
            for row in rows:
                connection.execute("""
                    INSERT OR IGNORE INTO legacy_recovery_v3
                        (legacy_source,legacy_id,symbol,scan_date,status,reason,resolved_at)
                    VALUES (?,?,?,?, 'IRRECOVERABLE', ?,?)
                """, (source, row["id"], row["ticker"], row["scan_date"], reason, resolved_at))
        return [{
            "legacy_source": source,
            "legacy_id": row["id"],
            "symbol": row["ticker"],
            "scan_date": row["scan_date"],
            "status": "IRRECOVERABLE",
            "reason": reason,
            "resolved_at": resolved_at,
        } for row in rows]

    def audit_snapshot(self) -> dict[str, Any]:
        with self._connection() as connection:
            predictions = connection.execute("SELECT COUNT(*) FROM predictions_v3").fetchone()[0]
            statuses = dict(connection.execute(
                "SELECT status,COUNT(*) FROM prediction_results_v3 GROUP BY status"
            ).fetchall())
            legacy = connection.execute("SELECT COUNT(*) FROM legacy_recovery_v3").fetchone()[0]
            feedback = connection.execute("SELECT COUNT(*) FROM prediction_feedback_v3").fetchone()[0]
        return {"predictions": predictions, "statuses": statuses, "legacy_resolutions": legacy, "feedback": feedback}
