"""Proceso independiente para las tareas intensivas y periódicas de /bolsa."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "database" / "bolsa_worker_status.json"
LOCK_PORT = int(os.environ.get("BOLSA_WORKER_LOCK_PORT", "5062"))
_stop = threading.Event()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def detect_compute_backend() -> dict:
    """Describe el hardware sin prometer CUDA para un modelo CPU-only."""
    gpu = {"available": False, "name": None, "memory_mb": None}
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0 and completed.stdout.strip():
            name, memory = [part.strip() for part in completed.stdout.splitlines()[0].split(",", 1)]
            gpu = {"available": True, "name": name, "memory_mb": int(float(memory))}
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return {
        "backend": "cpu",
        "reason": "sklearn_gradient_boosting_cpu_only",
        "gpu": gpu,
    }


def _write_status(payload: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, STATUS_FILE)


def _acquire_singleton() -> socket.socket:
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    lock.bind(("127.0.0.1", LOCK_PORT))
    lock.listen(1)
    return lock


def run() -> int:
    try:
        lock = _acquire_singleton()
    except OSError:
        print("[BOLSA-WORKER] Ya existe un proceso automático activo.")
        return 0

    from src.server import AUTO_SCAN_STATE, SCAN_STATE, start_background_tasks

    started_at = _utc_now()
    compute = detect_compute_backend()

    def request_stop(*_args):
        _stop.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    start_background_tasks()
    print(f"[BOLSA-WORKER] PID {os.getpid()} activo; cálculo={compute['backend']}.")
    try:
        while not _stop.wait(2):
            _write_status({
                "status": "running",
                "pid": os.getpid(),
                "started_at_utc": started_at,
                "heartbeat_utc": _utc_now(),
                "scheduler": dict(AUTO_SCAN_STATE),
                "scan": {
                    "is_scanning": bool(SCAN_STATE.get("is_scanning")),
                    "progress": float(SCAN_STATE.get("progress") or 0.0),
                    "message": SCAN_STATE.get("message") or "",
                    "results_count": len(SCAN_STATE.get("results") or []),
                    "generated_at_utc": SCAN_STATE.get("generated_at_utc"),
                },
                "compute": compute,
            })
    finally:
        _write_status({"status": "stopped", "pid": os.getpid(), "heartbeat_utc": _utc_now(), "compute": compute})
        lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
