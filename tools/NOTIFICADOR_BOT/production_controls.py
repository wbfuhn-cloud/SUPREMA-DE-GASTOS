"""Controles operativos y de seguridad para Inversiones IA 3.0."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def correlation_id(value: str | None = None) -> str:
    candidate = (value or "").strip()
    return candidate[:128] if candidate and all(char.isalnum() or char in "-_" for char in candidate) else str(uuid.uuid4())


def authorized_write(expected_token: str | None, authorization_header: str | None,
                     environment: str = "development") -> bool:
    """En producción se cierra por defecto; desarrollo sigue siendo local-compatible."""
    if not expected_token:
        return environment.lower() not in {"production", "prod"}
    supplied = (authorization_header or "").removeprefix("Bearer ").strip()
    return hmac.compare_digest(expected_token, supplied)


class RateLimiter:
    def __init__(self, limit: int = 60, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        instant = time.monotonic() if now is None else now
        queue = self._requests[key]
        while queue and instant - queue[0] >= self.window_seconds:
            queue.popleft()
        if len(queue) >= self.limit:
            return False
        queue.append(instant)
        return True


@dataclass
class OperationalMetrics:
    endpoint_latency_ms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    endpoint_errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    signal_count: int = 0
    stale_data_count: int = 0
    price_discrepancy_count: int = 0

    def observe(self, endpoint: str, latency_ms: float, status_code: int) -> None:
        values = self.endpoint_latency_ms[endpoint]
        values.append(float(latency_ms))
        if len(values) > 2000:
            del values[:-2000]
        if status_code >= 500:
            self.endpoint_errors[endpoint] += 1

    def snapshot(self) -> dict[str, Any]:
        p95 = {}
        for endpoint, values in self.endpoint_latency_ms.items():
            ordered = sorted(values)
            p95[endpoint] = ordered[max(0, int(len(ordered) * .95) - 1)] if ordered else None
        return {"latency_p95_ms": p95, "errors": dict(self.endpoint_errors),
                "signal_count": self.signal_count, "stale_data_count": self.stale_data_count,
                "price_discrepancy_count": self.price_discrepancy_count}


class KillSwitch:
    def __init__(self, state_path: str | Path):
        self.state_path = Path(state_path)

    def set(self, active: bool, reason: str, actor: str) -> dict[str, Any]:
        payload = {"active": bool(active), "reason": reason, "actor": actor,
                   "changed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return payload

    def status(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"active": False, "reason": None, "actor": None, "changed_at_utc": None}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def enforce(self, signal: dict[str, Any]) -> dict[str, Any]:
        status = self.status()
        if not status["active"]:
            return signal
        return {**signal, "state": "SIN SEÑAL", "kill_switch_active": True,
                "kill_switch_reason": status["reason"]}


def promotion_record(model_hash: str, evidence: dict[str, Any], approver: str,
                     decision: str) -> dict[str, Any]:
    if not approver.strip() or decision not in {"APPROVE", "REJECT"}:
        raise ValueError("Toda promoción requiere aprobador humano y decisión explícita")
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str)
    return {"model_hash": model_hash, "evidence_hash": hashlib.sha256(canonical.encode()).hexdigest(),
            "approver": approver, "decision": decision,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
