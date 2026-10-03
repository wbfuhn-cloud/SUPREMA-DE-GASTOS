"""Semáforo explicable para posiciones existentes del portafolio."""

from __future__ import annotations

from typing import Any


def classify_portfolio_position(*, pl_pct: float | None, signal_state: str | None,
                                signal_eligible: bool, data_quality: float,
                                is_leveraged: bool = False,
                                quote_adjusted: bool = True) -> dict[str, Any]:
    """Clasifica una posición sin confundir ganancia nominal con acierto de IA."""
    state = str(signal_state or "SIN SEÑAL").upper()
    quality_ok = data_quality >= 0.95
    corporate_action_risk = is_leveraged and not quote_adjusted
    trusted = quality_ok and signal_eligible and not corporate_action_risk
    loss = float(pl_pct) if pl_pct is not None else None

    if loss is not None and loss <= -10.0:
        return {
            "color": "red",
            "label": "SALIDA PRIORITARIA",
            "reason": "Pérdida de 10% o más; se activó el límite de protección.",
            "confidence": "normal" if trusted else "baja: validar precio antes de ejecutar",
            "pnl_reliable": trusted,
        }

    if trusted and state in {"SALIR", "REDUCIR"}:
        reason = ("El motor detecta deterioro o agotamiento y recomienda salir."
                  if state == "SALIR" else
                  "El objetivo de ganancia o el riesgo exige reducir la posición.")
        return {"color": "red", "label": "VENTA / REDUCIR", "reason": reason,
                "confidence": "normal", "pnl_reliable": True}

    if not trusted:
        if corporate_action_risk:
            reason = "ETF apalancado con precio/cantidad sin ajuste corporativo confirmado."
        elif not quality_ok:
            reason = "La cotización no alcanza 95% de calidad; no se permite decidir compra o venta técnica."
        else:
            reason = "No existe una señal elegible y auditable para esta posición."
        return {"color": "yellow", "label": "ESPERAR / VALIDAR", "reason": reason,
                "confidence": "insuficiente", "pnl_reliable": False}

    if loss is not None and loss > 0 and state in {"MANTENER", "COMPRAR"}:
        return {"color": "green", "label": "VA BIEN", "reason":
                "La posición tiene ganancia y no existe un gatillo confirmado de salida.",
                "confidence": "normal", "pnl_reliable": True}

    return {"color": "yellow", "label": "ESPERAR", "reason":
            "La evidencia aún no confirma continuación ni salida prioritaria.",
            "confidence": "normal", "pnl_reliable": trusted}
