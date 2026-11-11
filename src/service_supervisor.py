"""Arranque y cierre de servicios auxiliares en procesos aislados."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import logging
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "database" / "bolsa_worker.log"


def _spawn_bolsa_worker() -> subprocess.Popen:
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


class BolsaSupervisor:
    """Reinicia un worker caído mientras la aplicación siga abierta."""
    def __init__(self):
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.process = _spawn_bolsa_worker()
        self.thread = threading.Thread(target=self._watch, name="BolsaSupervisor", daemon=True)
        self.thread.start()

    @property
    def pid(self):
        return self.process.pid

    def poll(self):
        return self.process.poll()

    def _watch(self):
        while not self._stop.wait(5):
            with self._lock:
                code = self.process.poll()
                # 0: otro proceso ya posee el singleton; no iniciar duplicados.
                if code == 0:
                    return
                if code is not None and not self._stop.is_set():
                    logging.warning("Bolsa terminó con código %s; reiniciando.", code)
                    try:
                        self.process = _spawn_bolsa_worker()
                    except OSError:
                        logging.exception("No se pudo reiniciar Bolsa; se reintentará.")

    def stop(self, timeout=10.0):
        self._stop.set()
        with self._lock:
            stop_bolsa_worker(self.process, timeout)
        self.thread.join(timeout=6)


def start_bolsa_worker() -> BolsaSupervisor:
    return BolsaSupervisor()


def stop_bolsa_worker(process: subprocess.Popen | None, timeout: float = 10.0) -> None:
    """Detiene solamente el worker creado por este proceso supervisor."""
    if isinstance(process, BolsaSupervisor):
        process.stop(timeout)
        return
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
