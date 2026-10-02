"""Clasificación y registro seguro de errores de Inversiones IA."""

from __future__ import annotations

import re
from collections import Counter, deque
from datetime import datetime, timezone
from typing import Any


ERROR_CATEGORIES = {
    "DOM_NULL": "Elemento de interfaz ausente o todavía no disponible",
    "NETWORK_API": "Fallo de red, timeout o respuesta HTTP",
    "DATA_CONTRACT": "Dato ausente, inválido o incompatible",
    "AUTH_SECURITY": "Autenticación, autorización o límite de solicitudes",
    "FINANCIAL_ENGINE": "Motor de señales, riesgo o datos de mercado",
    "RENDERING": "Renderizado, estilos, iconos o navegador",
    "UNKNOWN": "Error no clasificado",
}

_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\(?:[^\\\s]+\\)*[^\s:]+")
_UNIX_PATH = re.compile(r"(?<!https:)(?<!http:)/(?:home|Users|var|tmp)/[^\s:]+")


def sanitize_public_error(value: Any, limit: int = 500) -> str:
    text = str(value or "Error sin detalle")
    text = _WINDOWS_PATH.sub("[ruta local oculta]", text)
    text = _UNIX_PATH.sub("[ruta local oculta]", text)
    return text[:limit]


def classify_error(message: Any, *, status_code: int | None = None,
                   component: str = "") -> dict[str, str]:
    safe = sanitize_public_error(message)
    lowered = safe.lower()
    if status_code in {401, 403, 429} or any(word in lowered for word in ("unauthorized", "no autorizado", "csrf", "rate limit")):
        category = "AUTH_SECURITY"
    elif any(word in lowered for word in ("null", "undefined", "classlist", "queryselector", "elemento")):
        category = "DOM_NULL"
    elif status_code is not None and status_code >= 400 or any(word in lowered for word in ("fetch", "network", "timeout", "http ", "conexión")):
        category = "NETWORK_API"
    elif any(word in lowered for word in ("schema", "contract", "nan", "invalid", "faltante", "missing")):
        category = "DATA_CONTRACT"
    elif any(word in lowered for word in ("ticker", "quote", "signal", "riesgo", "market", "modelo")):
        category = "FINANCIAL_ENGINE"
    elif any(word in lowered for word in ("render", "style", "lucide", "canvas", "webgl")):
        category = "RENDERING"
    else:
        category = "UNKNOWN"
    return {"category": category, "description": ERROR_CATEGORIES[category],
            "message": safe, "component": sanitize_public_error(component, 100)}


class ErrorRegistry:
    def __init__(self, max_items: int = 200):
        self._items: deque[dict[str, Any]] = deque(maxlen=max_items)

    def record(self, error: dict[str, Any]) -> dict[str, Any]:
        classified = classify_error(error.get("message"), status_code=error.get("status_code"),
                                    component=str(error.get("component") or "client"))
        item = {**classified,
                "source": sanitize_public_error(error.get("source"), 150),
                "line": error.get("line"),
                "correlation_id": sanitize_public_error(error.get("correlation_id"), 128),
                "occurred_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        self._items.append(item)
        return item

    def summary(self) -> dict[str, Any]:
        counts = Counter(item["category"] for item in self._items)
        return {"total": len(self._items), "by_category": dict(counts),
                "recent": list(self._items)[-20:]}
