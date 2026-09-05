"""
email_watcher.py -- Servicio de monitoreo continuo de correos BAZ Digital
=========================================================================
Corre en background y revisa el correo cada N minutos (configurado en .env).
Lanzado automaticamente desde start.bat.
"""

import os
import sys
import time
import logging
from datetime import datetime

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# -- Path setup -------------------------------------------------------
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

from src.email_reader import EmailReader

# -- Configuracion ----------------------------------------------------
CHECK_INTERVAL_MINUTES = int(os.getenv('EMAIL_CHECK_INTERVAL', '5'))
CHECK_INTERVAL_SECONDS = CHECK_INTERVAL_MINUTES * 60

# -- Logging ----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('EmailWatcher')


def main():
    print("=" * 62)
    print("  ASISTENTE FINANCIERO -- Monitor de Correos BAZ Digital")
    print(f"  Revisando cada {CHECK_INTERVAL_MINUTES} minuto(s)")
    print("  Presiona Ctrl+C para detener")
    print("=" * 62)

    reader = EmailReader()
    run_count = 0

    while True:
        run_count = run_count + 1
        now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        print(f"\n[{now_str}] Revision #{run_count}...")

        try:
            imported = reader.run_once(test_mode=False)
            if imported > 0:
                print(f"[{now_str}] {imported} gasto(s) nuevos importados desde BAZ!")
            else:
                print(f"[{now_str}] Sin correos nuevos.")
        except Exception as e:
            log.error(f"Error en revision #{run_count}: {e}", exc_info=True)

        print(f"   Proxima revision en {CHECK_INTERVAL_MINUTES} min...")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor detenido por el usuario.")
        sys.exit(0)
