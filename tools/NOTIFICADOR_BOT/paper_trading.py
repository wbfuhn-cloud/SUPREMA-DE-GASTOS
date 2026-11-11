"""Registro prospectivo y simulación de paper trading para Inversiones IA 3.0.

El ledger es append-only desde la API pública: una señal se identifica por el hash
de decisión producido por el motor de fusión y nunca se sobrescribe.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


PAPER_PROTOCOL_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def freeze_protocol(configuration: dict[str, Any]) -> dict[str, Any]:
    """Crea un manifiesto reproducible de modelo, features, umbrales y reglas."""
    canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "protocol_version": PAPER_PROTOCOL_VERSION,
        "configuration": configuration,
        "configuration_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


@dataclass(frozen=True)
class ExecutionObservation:
    decision_hash: str
    executable_price: float
    observed_spread_bps: float
    latency_ms: int
    slippage_bps: float = 0.0
    executed_at_utc: str | None = None


class PaperTradingLedger:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS paper_signals (
                    decision_hash TEXT PRIMARY KEY,
                    emitted_at_utc TEXT NOT NULL,
                    market_session TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    quoted_price REAL,
                    data_timestamp_utc TEXT,
                    provider TEXT,
                    data_quality REAL NOT NULL,
                    baseline_signal TEXT,
                    candidate_signal TEXT,
                    model_version TEXT NOT NULL,
                    rules_version TEXT NOT NULL,
                    protocol_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_executions (
                    decision_hash TEXT PRIMARY KEY REFERENCES paper_signals(decision_hash),
                    executed_at_utc TEXT NOT NULL,
                    executable_price REAL NOT NULL,
                    spread_bps REAL NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    slippage_bps REAL NOT NULL,
                    entry_deviation_bps REAL
                );
                CREATE TABLE IF NOT EXISTS paper_incidents (
                    incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opened_at_utc TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    closed_at_utc TEXT
                );
                CREATE TABLE IF NOT EXISTS kill_switch_drills (
                    drill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_at_utc TEXT NOT NULL,
                    trigger_name TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    details TEXT NOT NULL
                );
            """)

    def append_signal(self, signal: dict[str, Any], protocol_hash: str) -> bool:
        """Añade una señal. Un duplicado se rechaza sin alterar el original."""
        required = ("decision_hash", "ticker", "signal", "horizon", "model_version", "rules_version")
        missing = [name for name in required if not signal.get(name)]
        if missing:
            raise ValueError(f"Campos obligatorios ausentes: {', '.join(missing)}")
        emitted = str(signal.get("emitted_at_utc") or _utc_now())
        session = datetime.fromisoformat(emitted.replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()
        payload = json.dumps(signal, sort_keys=True, separators=(",", ":"), default=str)
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO paper_signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (signal["decision_hash"], emitted, session, str(signal["ticker"]).upper(),
                     signal["signal"], signal["horizon"], signal.get("quoted_price"),
                     signal.get("data_timestamp_utc"), signal.get("provider"),
                     float(signal.get("data_quality", 0.0)), signal.get("baseline_signal"),
                     signal.get("candidate_signal"), signal["model_version"],
                     signal["rules_version"], protocol_hash, payload),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def record_execution(self, observation: ExecutionObservation) -> dict[str, Any]:
        if observation.executable_price <= 0 or observation.latency_ms < 0:
            raise ValueError("Precio ejecutable y latencia deben ser válidos")
        with self._connect() as db:
            signal = db.execute(
                "SELECT quoted_price FROM paper_signals WHERE decision_hash = ?",
                (observation.decision_hash,),
            ).fetchone()
            if signal is None:
                raise KeyError("La señal no existe en el ledger")
            quoted = signal["quoted_price"]
            deviation = None if not quoted else (observation.executable_price / quoted - 1.0) * 10_000
            db.execute(
                "INSERT INTO paper_executions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (observation.decision_hash, observation.executed_at_utc or _utc_now(),
                 observation.executable_price, observation.observed_spread_bps,
                 observation.latency_ms, observation.slippage_bps, deviation),
            )
        return {**asdict(observation), "entry_deviation_bps": deviation}

    def open_incident(self, severity: str, category: str, description: str) -> int:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO paper_incidents(opened_at_utc,severity,category,description) VALUES(?,?,?,?)",
                (_utc_now(), severity, category, description),
            )
            return int(cursor.lastrowid)

    def close_incident(self, incident_id: int) -> None:
        with self._connect() as db:
            db.execute("UPDATE paper_incidents SET closed_at_utc=? WHERE incident_id=?", (_utc_now(), incident_id))

    def record_kill_switch_drill(self, trigger: str, success: bool, details: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO kill_switch_drills(run_at_utc,trigger_name,success,details) VALUES(?,?,?,?)",
                (_utc_now(), trigger, int(success), details),
            )

    def metrics(self, now_utc: str | None = None) -> dict[str, Any]:
        now = datetime.fromisoformat((now_utc or _utc_now()).replace("Z", "+00:00"))
        with self._connect() as db:
            rows = db.execute("SELECT * FROM paper_signals ORDER BY emitted_at_utc").fetchall()
            executions = db.execute("SELECT * FROM paper_executions").fetchall()
            critical_open = db.execute(
                "SELECT COUNT(*) FROM paper_incidents WHERE severity='critical' AND closed_at_utc IS NULL"
            ).fetchone()[0]
            drills = db.execute("SELECT success FROM kill_switch_drills").fetchall()
        from prediction_ledger import NyseCalendar
        calendar = NyseCalendar()
        # Registros antiguos guardaban 'regular'. Recuperar su fecha desde la
        # emisión sin alterar el historial inmutable ni inventar observaciones.
        session_dates = {datetime.fromisoformat(row['emitted_at_utc'].replace('Z', '+00:00'))
                         .astimezone(ZoneInfo('America/New_York')).date() for row in rows}
        sessions = sum(calendar.is_session(day) for day in session_dates)
        stale = 0
        eligible = []
        duplicate_count = 0  # la PK hace imposible persistir duplicados
        for row in rows:
            payload = json.loads(row['payload_json'])
            quote = payload.get('quote')
            is_stale = True
            timestamp = row["data_timestamp_utc"]
            if quote:
                from market_data import ensure_quote_contract
                emitted = datetime.fromisoformat(row['emitted_at_utc'].replace('Z', '+00:00'))
                is_stale = ensure_quote_contract({'Quote': quote}, received_at=emitted)['is_stale']
            elif timestamp:
                observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                is_stale = (datetime.fromisoformat(row["emitted_at_utc"].replace("Z", "+00:00")) - observed).total_seconds() > 900
            stale += int(is_stale)
            if (not is_stale and row['data_quality'] >= .9
                    and payload.get('signal_eligible', True) is True
                    and row['signal'] in {'COMPRAR', 'SALIR', 'REDUCIR', 'MANTENER/ESPERAR', 'ESPERAR', 'MANTENER'}):
                eligible.append(row)
        executable = sum(row["signal"] in {"COMPRAR", "SALIR", "REDUCIR"} for row in eligible)
        latencies = [row["latency_ms"] for row in executions]
        deviations = [abs(row["entry_deviation_bps"]) for row in executions if row["entry_deviation_bps"] is not None]
        first = datetime.fromisoformat(rows[0]["emitted_at_utc"].replace("Z", "+00:00")) if rows else now
        observed_seconds = max(0.0, (now - first).total_seconds())
        return {
            "market_sessions": sessions,
            "observed_signals": len(rows),
            "eligible_signals": len(eligible),
            "positive_executable_signals": executable,
            "execution_observations": len(executions),
            "duplicate_signals": duplicate_count,
            "stale_data_used": stale,
            "open_critical_incidents": critical_open,
            "kill_switch_drills": len(drills),
            "kill_switch_success_rate": (sum(row["success"] for row in drills) / len(drills)) if drills else None,
            "average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
            "average_entry_deviation_bps": sum(deviations) / len(deviations) if deviations else None,
            "observation_hours": observed_seconds / 3600.0,
        }


def phase9_approval(metrics: dict[str, Any], *, availability: float | None,
                    live_backtest_deviation: float | None, net_expected_value: float | None,
                    drawdown_within_limit: bool | None) -> dict[str, Any]:
    checks = {
        "duration_60_sessions": metrics.get("market_sessions", 0) >= 60,
        "sample_300_75": metrics.get("eligible_signals", 0) >= 300 and metrics.get("positive_executable_signals", 0) >= 75,
        "availability_99_5": availability is not None and availability >= 0.995,
        "zero_duplicates": metrics.get("duplicate_signals") == 0,
        "zero_stale_data": metrics.get("stale_data_used") == 0,
        "backtest_live_within_20pct": live_backtest_deviation is not None and abs(live_backtest_deviation) <= 0.20,
        "positive_net_expected_value": net_expected_value is not None and net_expected_value > 0,
        "drawdown_within_limit": drawdown_within_limit is True,
        "zero_open_critical_incidents": metrics.get("open_critical_incidents") == 0,
        "kill_switch_100pct": metrics.get("kill_switch_drills", 0) > 0 and metrics.get("kill_switch_success_rate") == 1.0,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "approved": not failed,
        "decision": "APPROVED" if not failed else "EXTEND_PAPER_TRADING",
        "checks": checks,
        "failed": failed,
    }


def kill_switch_reason(*, daily_loss_pct: float, max_daily_loss_pct: float,
                       data_corrupt: bool, drift_detected: bool, provider_available: bool) -> str | None:
    if data_corrupt:
        return "DATA_CORRUPTION"
    if not provider_available:
        return "PROVIDER_OUTAGE"
    if drift_detected:
        return "MODEL_DRIFT"
    if not math.isfinite(daily_loss_pct) or daily_loss_pct <= -abs(max_daily_loss_pct):
        return "LOSS_LIMIT"
    return None
