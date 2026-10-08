"""Experimento autónomo y persistente de aprendizaje con paper trading."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from prediction_ledger import NyseCalendar


DEFAULT_WEIGHTS = {
    "technical_score": 1.0,
    "trend_momentum": 1.0,
    "liquidity": 1.0,
    "volatility_quality": 1.0,
}
HORIZONS = (21, 63, 126)


class AdaptivePaperExperiment:
    """Selecciona, mantiene y evalúa una posición ficticia; nunca opera dinero real."""

    def __init__(self, path: str | Path, learning_rate: float = 0.03):
        self.path = str(path)
        self.learning_rate = min(max(float(learning_rate), 0.005), 0.05)
        self.calendar = NyseCalendar()
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS adaptive_experiment_parameters (
                    version INTEGER PRIMARY KEY, created_at_utc TEXT NOT NULL,
                    weights_json TEXT NOT NULL, reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS adaptive_experiment_positions (
                    position_id TEXT PRIMARY KEY, ticker TEXT NOT NULL,
                    opened_session TEXT NOT NULL, due_session TEXT NOT NULL,
                    horizon_sessions INTEGER NOT NULL, entry_price REAL NOT NULL,
                    current_price REAL NOT NULL, status TEXT NOT NULL,
                    exit_price REAL, closed_session TEXT, return_pct REAL,
                    exit_reason TEXT, parameter_version INTEGER NOT NULL,
                    decision_score REAL NOT NULL, snapshot_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS adaptive_experiment_reviews (
                    review_id TEXT PRIMARY KEY, position_id TEXT NOT NULL,
                    reviewed_at_utc TEXT NOT NULL, outcome TEXT NOT NULL,
                    return_pct REAL NOT NULL, old_weights_json TEXT NOT NULL,
                    new_weights_json TEXT NOT NULL, explanation_json TEXT NOT NULL
                );
            """)
            exists = db.execute("SELECT 1 FROM adaptive_experiment_parameters LIMIT 1").fetchone()
            if not exists:
                db.execute(
                    "INSERT INTO adaptive_experiment_parameters VALUES(1,?,?,?)",
                    (self._now(), json.dumps(DEFAULT_WEIGHTS, sort_keys=True), "initial_defaults"),
                )
            db.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _parameters(self, db) -> tuple[int, dict[str, float]]:
        row = db.execute(
            "SELECT version,weights_json FROM adaptive_experiment_parameters ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return int(row["version"]), json.loads(row["weights_json"])

    @staticmethod
    def _features(row: dict[str, Any], horizon: dict[str, Any]) -> dict[str, float]:
        score = min(max(float(row.get("Score") or 0) / 100.0, 0.0), 1.0)
        momentum = min(max(float(horizon.get("historical_momentum_pct") or 0) / 30.0, -1.0), 1.0)
        liquidity = min(max(float(row.get("Vol_Ratio") or 0) / 2.0, 0.0), 1.0)
        volatility = float(row.get("Realized_Volatility_20d_Pct") or 0)
        volatility_quality = max(0.0, 1.0 - abs(volatility - 45.0) / 75.0)
        return {
            "technical_score": score,
            "trend_momentum": momentum,
            "liquidity": liquidity,
            "volatility_quality": volatility_quality,
        }

    def _candidate(self, rows: list[dict[str, Any]], weights: dict[str, float]):
        ranked = sorted(rows, key=lambda item: float(item.get("Realized_Volatility_20d_Pct") or 0), reverse=True)[:10]
        choices = []
        for row in ranked:
            if row.get("Is_Leveraged") or float(row.get("Data_Quality") or 0) < 0.80:
                continue
            if not (row.get("Historical_Coverage") or {}).get("eligible"):
                continue
            horizons = (row.get("Holding_Outlook") or {}).get("horizons") or {}
            for outlook in horizons.values():
                sessions = int(outlook.get("sessions") or 0)
                momentum = float(outlook.get("historical_momentum_pct") or 0)
                risk = max(float(outlook.get("estimated_move_1sigma_pct") or 0), 1.0)
                if sessions not in HORIZONS or momentum <= 0:
                    continue
                features = self._features(row, outlook)
                weighted = sum(weights[name] * value for name, value in features.items())
                decision_score = weighted + min(momentum / risk, 2.0)
                choices.append((decision_score, row, outlook, features))
        return max(choices, key=lambda item: item[0]) if choices else None

    def _learn(self, db, position: sqlite3.Row, return_pct: float):
        version, old = self._parameters(db)
        snapshot = json.loads(position["snapshot_json"])
        features = snapshot["features"]
        direction = 1.0 if return_pct > 0 else -1.0
        magnitude = min(abs(return_pct) / 30.0, 1.0)
        new = {
            name: round(min(max(old[name] + direction * self.learning_rate * magnitude * value, 0.50), 1.50), 6)
            for name, value in features.items()
        }
        new_version = version + 1
        db.execute(
            "INSERT INTO adaptive_experiment_parameters VALUES(?,?,?,?)",
            (new_version, self._now(), json.dumps(new, sort_keys=True), f"closed:{position['position_id']}"),
        )
        db.execute(
            "INSERT INTO adaptive_experiment_reviews VALUES(?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), position["position_id"], self._now(),
             "WIN" if return_pct > 0 else "LOSS", return_pct,
             json.dumps(old, sort_keys=True), json.dumps(new, sort_keys=True),
             json.dumps({"features": features, "bounded_learning_rate": self.learning_rate}, sort_keys=True)),
        )

    def run_cycle(self, rows: list[dict[str, Any]], session: date | None = None) -> dict[str, Any]:
        today = session or datetime.now(timezone.utc).date()
        prices = {str(row.get("Ticker") or "").upper(): float(row.get("Price") or 0) for row in rows}
        with self._connect() as db:
            position = db.execute(
                "SELECT * FROM adaptive_experiment_positions WHERE status='OPEN' ORDER BY opened_session LIMIT 1"
            ).fetchone()
            event = "NO_ACTION"
            if position and prices.get(position["ticker"], 0) > 0:
                current = prices[position["ticker"]]
                change = (current / float(position["entry_price"]) - 1.0) * 100.0
                due = date.fromisoformat(position["due_session"])
                reason = "HORIZON_COMPLETE" if today >= due else "STOP_LOSS" if change <= -15 else "TAKE_PROFIT" if change >= 30 else None
                if reason:
                    db.execute(
                        "UPDATE adaptive_experiment_positions SET status='CLOSED',current_price=?,exit_price=?,closed_session=?,return_pct=?,exit_reason=? WHERE position_id=?",
                        (current, current, today.isoformat(), change, reason, position["position_id"]),
                    )
                    self._learn(db, position, change)
                    event = "CLOSED_AND_LEARNED"
                    position = None
                else:
                    db.execute("UPDATE adaptive_experiment_positions SET current_price=? WHERE position_id=?", (current, position["position_id"]))
                    event = "HELD"
            if position is None and event != "CLOSED_AND_LEARNED":
                version, weights = self._parameters(db)
                choice = self._candidate(rows, weights)
                if choice:
                    decision_score, row, outlook, features = choice
                    opened = today
                    due = self.calendar.advance_sessions(opened, int(outlook["sessions"]))
                    position_id = str(uuid.uuid4())
                    snapshot = {"row": row, "outlook": outlook, "features": features, "weights": weights}
                    db.execute(
                        "INSERT INTO adaptive_experiment_positions VALUES(?,?,?,?,?,?,?,'OPEN',NULL,NULL,NULL,NULL,?,?,?)",
                        (position_id, str(row["Ticker"]).upper(), opened.isoformat(), due.isoformat(),
                         int(outlook["sessions"]), float(row["Price"]), float(row["Price"]),
                         version, float(decision_score), json.dumps(snapshot, sort_keys=True, default=str)),
                    )
                    event = "OPENED"
            db.commit()
        return {"event": event, **self.status()}

    def status(self) -> dict[str, Any]:
        with self._connect() as db:
            version, weights = self._parameters(db)
            open_position = db.execute(
                "SELECT * FROM adaptive_experiment_positions WHERE status='OPEN' LIMIT 1"
            ).fetchone()
            totals = db.execute(
                "SELECT COUNT(*) total,SUM(CASE WHEN return_pct>0 THEN 1 ELSE 0 END) wins,AVG(return_pct) average_return_pct FROM adaptive_experiment_positions WHERE status='CLOSED'"
            ).fetchone()
        return {
            "mode": "paper_only", "real_money": False,
            "parameter_version": version, "weights": weights,
            "open_position": dict(open_position) if open_position else None,
            "closed_positions": int(totals["total"] or 0),
            "wins": int(totals["wins"] or 0),
            "average_return_pct": totals["average_return_pct"],
        }

    def export_backup(self) -> str:
        """Serializa parámetros, posiciones y revisiones para respaldo remoto."""
        tables = (
            "adaptive_experiment_parameters",
            "adaptive_experiment_positions",
            "adaptive_experiment_reviews",
        )
        with self._connect() as db:
            payload = {
                "backup_version": 1,
                "exported_at_utc": self._now(),
                "tables": {
                    table: [dict(row) for row in db.execute(f"SELECT * FROM {table}")]
                    for table in tables
                },
            }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    def restore_backup(self, serialized: str) -> bool:
        """Restaura una copia cloud solo cuando contiene una versión más nueva."""
        payload = json.loads(serialized)
        if payload.get("backup_version") != 1:
            raise ValueError("Versión de respaldo adaptativo no soportada")
        tables = payload.get("tables") or {}
        remote_parameters = tables.get("adaptive_experiment_parameters") or []
        if not remote_parameters:
            return False
        remote_version = max(int(row["version"]) for row in remote_parameters)
        with self._connect() as db:
            local_version, _weights = self._parameters(db)
            local_positions = db.execute("SELECT COUNT(*) FROM adaptive_experiment_positions").fetchone()[0]
            if remote_version < local_version or (remote_version == local_version and local_positions > 0):
                return False
            for table in (
                "adaptive_experiment_reviews",
                "adaptive_experiment_positions",
                "adaptive_experiment_parameters",
            ):
                db.execute(f"DELETE FROM {table}")
            for table, rows in tables.items():
                if table not in {
                    "adaptive_experiment_parameters",
                    "adaptive_experiment_positions",
                    "adaptive_experiment_reviews",
                }:
                    continue
                for row in rows:
                    columns = list(row)
                    placeholders = ",".join("?" for _ in columns)
                    db.execute(
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                        [row[column] for column in columns],
                    )
        return True
