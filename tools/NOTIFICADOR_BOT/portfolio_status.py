"""Semáforo explicable para posiciones existentes del portafolio."""

from __future__ import annotations

from typing import Any


def classify_portfolio_position(*, pl_pct: float | None, signal_state: str | None,
                                signal_eligible: bool, data_quality: float,
                                is_leveraged: bool = False,
                                quote_adjusted: bool = True,
                                weekly_change_pct: float | None = None,
                                trend_state: str | None = None,
                                upside_scenario_3m_pct: float | None = None) -> dict[str, Any]:
    """Clasifica una posición sin confundir ganancia nominal con acierto de IA."""
    state = str(signal_state or "SIN SEÑAL").upper()
    quality_ok = data_quality >= 0.95
    corporate_action_risk = is_leveraged and not quote_adjusted
    trusted = quality_ok and signal_eligible and not corporate_action_risk
    loss = float(pl_pct) if pl_pct is not None else None
    weekly = float(weekly_change_pct) if weekly_change_pct is not None else None
    trend = str(trend_state or "SIN SEÑAL").upper()
    scenario = (round(float(upside_scenario_3m_pct), 1)
                if upside_scenario_3m_pct is not None else None)

    if loss is not None and loss <= -10.0:
        return {
            "color": "red",
            "label": "SALIDA PRIORITARIA",
            "reason": "Pérdida de 10% o más; se activó el límite de protección.",
            "summary": "VENDE O REDUCE: valida el precio y protege el capital antes de perder más.",
            "monitoring_note": "Si sales, el sistema seguirá observando una posible señal de reentrada.",
            "confidence": "normal" if trusted else "baja: validar precio antes de ejecutar",
            "pnl_reliable": trusted,
        }

    if trusted and state in {"SALIR", "REDUCIR"}:
        reason = ("El motor detecta deterioro o agotamiento y recomienda salir."
                  if state == "SALIR" else
                  "El objetivo de ganancia o el riesgo exige reducir la posición.")
        return {"color": "red", "label": "VENTA / REDUCIR", "reason": reason,
                "summary": "VENDE O REDUCE: la señal técnica se deterioró; evita devolver la ganancia o ampliar la pérdida.",
                "monitoring_note": "Te avisaré si la señal cambia y vuelve a permitir entrada.",
                "confidence": "normal", "pnl_reliable": True}

    if not trusted:
        if corporate_action_risk:
            reason = "ETF apalancado con precio/cantidad sin ajuste corporativo confirmado."
        elif not quality_ok:
            reason = "La cotización no alcanza 95% de calidad; no se permite decidir compra o venta técnica."
        else:
            reason = "No existe una señal elegible y auditable para esta posición."
        return {"color": "yellow", "label": "ESPERAR / VALIDAR", "reason": reason,
                "summary": "ESPERA: primero valida la cotización; con estos datos no es responsable prometer recuperación ni +40%.",
                "monitoring_note": "Actualizaré el resumen cuando exista una señal auditable.",
                "confidence": "insuficiente", "pnl_reliable": False}

    if loss is not None and loss > 0 and state in {"MANTENER", "COMPRAR"}:
        strong_week = weekly is not None and 2.0 <= weekly <= 5.0
        supportive_trend = trend in {"COMPRAR", "MANTENER", "MANTENER/ESPERAR"}
        if strong_week and supportive_trend:
            if scenario is not None and scenario >= 35.0:
                outlook = (f"El rango histórico permite un escenario extremo cercano a +{min(scenario, 40.0):.0f}% "
                           "a 3 meses; no es un pronóstico ni una garantía.")
            elif scenario is not None:
                outlook = f"El escenario alcista estimado a 3 meses ronda +{scenario:.1f}%; puede no cumplirse."
            else:
                outlook = "Una subida de +40% en 3 meses no está confirmada y sería un escenario especulativo."
            summary = f"AGUANTA: avanzó {weekly:+.1f}% en una semana y la tendencia continúa favorable. {outlook}"
        else:
            summary = "MANTÉN: la posición va en ganancia y todavía no aparece una salida confirmada."
        return {"color": "green", "label": "VA BIEN", "reason":
                "La posición tiene ganancia y no existe un gatillo confirmado de salida.",
                "summary": summary,
                "monitoring_note": "Te avisaré cuando aparezca una señal SALIR o REDUCIR; no esperes una ganancia fija.",
                "confidence": "normal", "pnl_reliable": True}

    if loss is not None and -10.0 < loss <= 0 and trend in {"COMPRAR", "MANTENER", "MANTENER/ESPERAR"}:
        return {"color": "yellow", "label": "ESPERAR", "reason":
                "La posición está debajo del precio de compra, pero la tendencia larga no confirma salida.",
                "summary": "DÉJALA EN OBSERVACIÓN: podría recuperarse en un horizonte de 4–5 meses, pero no está garantizado.",
                "monitoring_note": "No esperes ese plazo si alcanza -10% o aparece SALIR/REDUCIR; esas reglas tienen prioridad.",
                "confidence": "normal", "pnl_reliable": trusted}

    return {"color": "yellow", "label": "ESPERAR", "reason":
            "La evidencia aún no confirma continuación ni salida prioritaria.",
            "summary": "ESPERA: mantén la posición bajo observación; todavía no hay base para vender ni prometer recuperación.",
            "monitoring_note": "Te avisaré cuando la evidencia cambie a VA BIEN, REDUCIR o SALIR.",
            "confidence": "normal", "pnl_reliable": trusted}
