"""Carga la configuración de la instalación, independientemente del directorio actual."""
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'


def load_settings():
    load_dotenv(ENV_FILE, override=False)
