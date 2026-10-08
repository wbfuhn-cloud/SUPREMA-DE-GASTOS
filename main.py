import sys
from src.infra.encoding import force_utf8_encoding

force_utf8_encoding()

import threading
from src.bot import ExpenseBot
from src.config import Config
from src.server import run_server
from src.service_supervisor import start_bolsa_worker, stop_bolsa_worker

def main():
    bolsa_worker = None
    try:
        Config.validate()
        
        print("Iniciando servidor web...")
        server_thread = threading.Thread(
            target=run_server,
            kwargs={'host': '0.0.0.0', 'port': 5050, 'debug': False, 'start_jobs': False},
            daemon=True
        )
        server_thread.start()

        print("Iniciando proceso independiente de Bolsa...")
        bolsa_worker = start_bolsa_worker()
        
        print("Iniciando bot de Telegram...")
        bot = ExpenseBot(
            Config.TELEGRAM_TOKEN,
            Config.GOOGLE_API_KEY,
            Config.DASHBOARD_URL
        )
        bot.run()
        
    except ValueError as e:
        print(f"Error de configuración: {e}")
        print("\nAsegúrate de que el archivo .env existe y tiene las variables:")
        print("  - TELEGRAM_BOT_TOKEN")
        print("  - GOOGLE_API_KEY")
        input("\nPresiona Enter para salir...")
    except Exception as e:
        print(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresiona Enter para salir...")
    finally:
        stop_bolsa_worker(bolsa_worker)

if __name__ == "__main__":
    main()
