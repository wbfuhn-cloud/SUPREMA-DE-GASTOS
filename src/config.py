import os
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv(override=True)

class Config:
    """
    Clase central para manejar la configuración del proyecto.
    Carga variables de entorno y define valores por defecto.
    """
    
    # Credenciales y Claves
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # Base de Datos SQLite
    DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        "database", 
        "expenses.db"
    ))
    
    # Directorios
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
    
    # URL del Dashboard — se establece dinámicamente al arrancar (app.py).
    # El fallback usa localhost:5050; la IP real de red se detecta automáticamente.
    DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://127.0.0.1:5050/dashboard")

    # Configuración de Unidades (DEPRECATED)
    UNITS_CONFIG_PATH = os.path.join(BASE_DIR, "src", "units_config.json")

    @classmethod
    def get_units_config(cls):
        """Fallback para compatibilidad legacy."""
        return ["GENERAL"], "GENERAL", True

    @classmethod
    def save_units_config(cls, units, default_unit, setup_completed=True):
        """Placeholder para compatibilidad legacy."""
        return True, "Configuración guardada (Legacy)"

    @classmethod
    def validate(cls):
        """Valida que las credenciales críticas existan."""
        missing = []
        if not cls.TELEGRAM_TOKEN or "TU_TOKEN" in cls.TELEGRAM_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.GOOGLE_API_KEY or "TU_API_KEY" in cls.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
            
        if missing:
            raise ValueError(f"Faltan configuraciones críticas en .env: {', '.join(missing)}")
        return True
