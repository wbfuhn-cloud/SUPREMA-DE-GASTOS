"""Verificación secundaria gratuita de cotizaciones mediante Nasdaq.

Yahoo continúa siendo la fuente canónica del análisis histórico. Nasdaq se usa
únicamente como control independiente de las candidatas principales, sin clave
API y con caché para no abusar del servicio público.
"""

from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests


NASDAQ_URL = "https://api.nasdaq.com/api/quote/{symbol}/info?assetclass=stocks"
CACHE_SECONDS = 15 * 60
PRICE_TOLERANCE_PCT = 1.0
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _number(value: Any) -> float:
    cleaned = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if not cleaned:
        raise ValueError("precio secundario ausente")
    return float(cleaned)


def _timestamp(value: Any) -> str | None:
    text = re.sub(r"\s+ET$", "", str(value or "").strip())
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%b %d, %Y %I:%M %p")
        parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def fetch_nasdaq_quote(symbol: str, timeout: float = 6.0) -> dict[str, Any]:
    """Obtiene una cotización pública de Nasdaq; nunca requiere una API key."""
    normalized = str(symbol).upper().replace(".", "-")
    now = time.time()
    with _cache_lock:
        cached = _cache.get(normalized)
        if cached and now - cached[0] < CACHE_SECONDS:
            return {**cached[1], "cached": True}

    response = requests.get(
        NASDAQ_URL.format(symbol=normalized), headers=_HEADERS, timeout=timeout
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    primary = data.get("primaryData") or {}
    result = {
        "available": True,
        "provider": "nasdaq_public",
        "symbol": str(data.get("symbol") or normalized).upper().replace("-", "."),
        "price": _number(primary.get("lastSalePrice")),
        "market_timestamp": _timestamp(primary.get("lastTradeTimestamp")),
        "is_real_time": bool(primary.get("isRealTime")),
        "market_status": data.get("marketStatus"),
        "cached": False,
    }
    with _cache_lock:
        _cache[normalized] = (now, result)
    return result


def verify_quote(primary: Mapping[str, Any]) -> dict[str, Any]:
    symbol = str(primary.get("symbol") or "").upper()
    base = {"provider": "nasdaq_public", "checked": False,
            "status": "unavailable",
            "message": "Nasdaq no pudo confirmar esta cotización"}
    try:
        secondary = fetch_nasdaq_quote(symbol)
        first = float(primary.get("price") or 0)
        second = float(secondary["price"])
        midpoint = (abs(first) + abs(second)) / 2
        difference = 0.0 if midpoint == 0 else abs(first - second) / midpoint * 100
        agrees = difference <= PRICE_TOLERANCE_PCT
        return {
            **base, **secondary, "checked": True,
            "status": "confirmed" if agrees else "conflict",
            "consistent": agrees, "difference_pct": round(difference, 3),
            "tolerance_pct": PRICE_TOLERANCE_PCT,
            "primary_provider": primary.get("provider"), "primary_price": first,
            "message": ("Precio confirmado por una segunda fuente" if agrees else
                        "Los proveedores difieren; revisar antes de operar"),
        }
    except Exception as exc:
        return {**base, "error": type(exc).__name__}


def verify_top_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Verifica en paralelo una lista pequeña y conserva el orden recibido."""
    selected = rows[:max(0, min(int(limit), 10))]
    output = [dict(row) for row in selected]
    with ThreadPoolExecutor(max_workers=min(4, len(selected) or 1)) as executor:
        pending = {
            executor.submit(verify_quote, row.get("Quote") or {
                "symbol": row.get("Ticker"), "price": row.get("Price"),
                "provider": "yahoo_chart_v8"}): index
            for index, row in enumerate(selected)
        }
        for future in as_completed(pending):
            output[pending[future]]["Secondary_Verification"] = future.result()
    return output
