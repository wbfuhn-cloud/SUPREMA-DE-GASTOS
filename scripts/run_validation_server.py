"""Servidor local de validación; nunca habilita debug ni reloader."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.server import app


if __name__ == "__main__":
    port = int(os.getenv("VALIDATION_PORT", "5051"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
