"""Monitor de correos BAZ Digital para importar gastos automáticamente."""

import logging
import os
import sys
import threading

from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

try:
    from src.email_reader import EmailReader
except ImportError:
    EmailReader = None

log_baz = logging.getLogger("BAZ-Monitor")
stop_event = threading.Event()
EMAIL_INTERVALO = int(os.getenv("EMAIL_CHECK_INTERVAL", "5")) * 60


def hilo_baz():
    """Revisa periódicamente el correo e importa los gastos nuevos."""
    if EmailReader is None:
        log_baz.error("EmailReader no disponible.")
        return

    try:
        reader = EmailReader()
    except Exception as exc:
        log_baz.error("No se pudo inicializar EmailReader: %s", exc)
        return

    log_baz.info("Monitor BAZ iniciado. Revisando cada %s min.", EMAIL_INTERVALO // 60)
    run = 0
    while not stop_event.is_set():
        run += 1
        try:
            imported = reader.run_once(test_mode=False)
            if imported > 0:
                log_baz.info("Revisión #%s: %s gasto(s) nuevos importados.", run, imported)
            else:
                log_baz.debug("Revisión #%s: sin correos nuevos.", run)
        except Exception as exc:
            log_baz.error("Error en revisión #%s: %s", run, exc, exc_info=True)
        stop_event.wait(timeout=EMAIL_INTERVALO)


def main():
    """Ejecuta únicamente el monitor de correo cuando se lanza este módulo."""
    logging.basicConfig(level=logging.INFO)
    try:
        hilo_baz()
    except KeyboardInterrupt:
        stop_event.set()


if __name__ == "__main__":
    main()
