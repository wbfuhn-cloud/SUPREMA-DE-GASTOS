"""Persistencia compartida del portafolio mediante el almacén de ajustes."""

from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone
from typing import Any


PORTFOLIO_SETTING_KEY = "bolsa.portfolio.v1"


def normalize_portfolio(value: Any) -> dict[str, dict[str, Any]]:
    """Normaliza el formato histórico y descarta posiciones inválidas."""
    if isinstance(value, list):
        value = {ticker: {"qty": 0, "avg_price": 0} for ticker in value}
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for raw_ticker, raw_position in value.items():
        ticker = str(raw_ticker or "").strip().upper()
        if not ticker or not isinstance(raw_position, dict):
            continue
        try:
            qty = float(raw_position.get("qty", 0))
            avg_price = float(raw_position.get("avg_price", raw_position.get("price", 0)))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(qty) or not math.isfinite(avg_price) or qty < 0 or avg_price < 0:
            continue
        normalized[ticker] = {
            "qty": qty,
            "avg_price": avg_price,
            "updated_at": str(raw_position.get("updated_at") or ""),
        }
    return normalized


class PortfolioSync:
    """Mantiene D1 como fuente compartida y el JSON local como respaldo."""

    def __init__(self, config_manager, settings_store):
        self.config_manager = config_manager
        self.settings_store = settings_store
        self._lock = threading.RLock()

    @property
    def backend(self) -> str:
        return str(getattr(self.settings_store, "storage_mode", "unknown"))

    def _save_local(self, portfolio: dict[str, dict[str, Any]]) -> None:
        self.config_manager.config["portfolio"] = portfolio
        self.config_manager.save_config()

    def _metadata(self, *, available: bool, persisted: bool, source: str,
                  message: str = "") -> dict[str, Any]:
        return {
            "backend": self.backend,
            "cloud_available": available and self.backend == "cloud",
            "synchronized": persisted and self.backend == "cloud",
            "source": source,
            "message": message,
        }

    def load(self, migrate_local: bool = True) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        with self._lock:
            available, raw = self.settings_store.get_setting_status(PORTFOLIO_SETTING_KEY)
            local = normalize_portfolio(self.config_manager.get_portfolio())
            if not available:
                return local, self._metadata(
                    available=False, persisted=False, source="local_fallback",
                    message="La nube no está disponible; se muestra la copia local.",
                )

            if raw is not None:
                try:
                    payload = json.loads(raw)
                    remote_value = payload.get("portfolio", payload) if isinstance(payload, dict) else {}
                    remote = normalize_portfolio(remote_value)
                    self._save_local(remote)
                    return remote, self._metadata(
                        available=True, persisted=True, source=self.backend,
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    return local, self._metadata(
                        available=True, persisted=False, source="local_fallback",
                        message="El portafolio remoto tiene un formato inválido.",
                    )

            if migrate_local and local:
                return self.save(local)
            return local, self._metadata(
                available=True, persisted=self.backend == "cloud", source=self.backend,
            )

    def save(self, portfolio: Any) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        with self._lock:
            normalized = normalize_portfolio(portfolio)
            payload = json.dumps({
                "schema_version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "portfolio": normalized,
            }, ensure_ascii=False, sort_keys=True)
            success, message = self.settings_store.set_setting(PORTFOLIO_SETTING_KEY, payload)
            if not success:
                return normalize_portfolio(self.config_manager.get_portfolio()), self._metadata(
                    available=False, persisted=False, source="local_fallback", message=message,
                )
            self._save_local(normalized)
            return normalized, self._metadata(
                available=True, persisted=True, source=self.backend, message=message,
            )

    def update(self, ticker: str, qty: float, avg_price: float):
        with self._lock:
            portfolio, read_meta = self.load(migrate_local=True)
            if not read_meta["cloud_available"] and self.backend == "cloud":
                return portfolio, read_meta
            portfolio[str(ticker).strip().upper()] = {
                "qty": float(qty),
                "avg_price": float(avg_price),
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            return self.save(portfolio)

    def remove(self, ticker: str):
        with self._lock:
            portfolio, read_meta = self.load(migrate_local=True)
            if not read_meta["cloud_available"] and self.backend == "cloud":
                return portfolio, read_meta
            portfolio.pop(str(ticker).strip().upper(), None)
            return self.save(portfolio)
