"""Arranque y cierre de servicios auxiliares en procesos aislados."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "database" / "bolsa_worker.log"


def start_bolsa_worker() -> subprocess.Popen:
    """Inicia el worker oculto; su bloqueo interno evita duplicados."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_FILE.open("a", encoding="utf-8")
    kwargs = {
        "cwd": str(ROOT),
        "env": os.environ.copy(),
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen([sys.executable, "-m", "src.bolsa_worker"], **kwargs)
    log_handle.close()
    return process


def stop_bolsa_worker(process: subprocess.Popen | None, timeout: float = 10.0) -> None:
    """Detiene solamente el worker creado por este proceso supervisor."""
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
