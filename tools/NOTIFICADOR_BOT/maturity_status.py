"""Estado legible de madurez para el visor de inversiones.

Separa la implementación técnica de la validación operativa. Terminar el
código no equivale a estar aprobado para operar con dinero real.
"""

from __future__ import annotations

import math
from typing import Any


MIN_DATA_QUALITY = 0.95
MIN_SESSIONS = 60
MIN_SIGNALS = 300
MIN_EXECUTABLE_SIGNALS = 75


def _ratio(value: Any, target: int) -> float:
    try:
        return min(max(float(value or 0) / target, 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _data_quality(results: list[dict[str, Any]]) -> dict[str, Any]:
    values = []
    for row in results:
        value = row.get("Data_Quality")
        if value is None:
            value = (row.get("Quote") or {}).get("quality_score")
        try:
            numeric = float(value)
            if math.isfinite(numeric):
                values.append(numeric)
        except (TypeError, ValueError):
            continue
    passing = sum(value >= MIN_DATA_QUALITY for value in values)
    return {
        "observed": len(values),
        "passing": passing,
        "minimum": min(values) if values else None,
        "average": (sum(values) / len(values)) if values else None,
        "threshold": MIN_DATA_QUALITY,
        "approved": bool(values) and passing == len(values),
    }


def build_maturity_status(*, paper_metrics: dict[str, Any], paper_gate: dict[str, Any],
                          release_gate: dict[str, Any],
                          scan_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Construye el semáforo de fase sólo con evidencia observable."""
    quality = _data_quality(scan_results)
    sessions = int(paper_metrics.get("market_sessions") or 0)
    signals = int(paper_metrics.get("eligible_signals") or 0)
    executable = int(paper_metrics.get("positive_executable_signals") or 0)
    paper_checks = paper_gate.get("checks") or {}
    paper_check_ratio = (sum(value is True for value in paper_checks.values()) / len(paper_checks)
                         if paper_checks else 0.0)

    evidence = {
        "data_quality": quality,
        "market_sessions": {"current": sessions, "required": MIN_SESSIONS,
                            "approved": sessions >= MIN_SESSIONS},
        "eligible_signals": {"current": signals, "required": MIN_SIGNALS,
                             "approved": signals >= MIN_SIGNALS},
        "executable_signals": {"current": executable, "required": MIN_EXECUTABLE_SIGNALS,
                               "approved": executable >= MIN_EXECUTABLE_SIGNALS},
        "paper_checks": {"passed": sum(value is True for value in paper_checks.values()),
                         "total": len(paper_checks), "approved": paper_gate.get("approved") is True},
    }

    release_approved = release_gate.get("approved_for_production") is True
    paper_approved = paper_gate.get("approved") is True
    progress_parts = [
        1.0 if quality["approved"] else 0.0,
        _ratio(sessions, MIN_SESSIONS),
        _ratio(signals, MIN_SIGNALS),
        _ratio(executable, MIN_EXECUTABLE_SIGNALS),
        paper_check_ratio,
        1.0 if release_approved else 0.0,
    ]
    evidence_score = round(sum(progress_parts) / len(progress_parts) * 100)

    if release_approved:
        phase = {"number": 12, "name": "Liberación controlada", "state": "APROBADA"}
        solidity = {"level": "SOLIDO", "label": "Validado para producción",
                    "score": 100, "real_money_enabled": bool(release_gate.get("real_money_enabled"))}
        next_step = {"code": "MONITOR", "label": "Monitorear producción y rollback",
                     "detail": "Mantener vigilancia de errores, latencia, datos vencidos y deriva."}
    elif paper_approved:
        phase = {"number": 10, "name": "Validación UX y operativa", "state": "PENDIENTE"}
        solidity = {"level": "CANDIDATO", "label": "Candidato; falta aprobación final",
                    "score": min(evidence_score, 94), "real_money_enabled": False}
        next_step = {"code": "FINAL_GATES", "label": "Completar evidencia UX, operación y revisión humana",
                     "detail": "Cerrar los gates pendientes antes de una liberación controlada."}
    else:
        phase = {"number": 9, "name": "Paper trading y evidencia prospectiva", "state": "EN_CURSO"}
        solidity = {"level": "EN_VALIDACION" if (sessions or signals) else "EXPERIMENTAL",
                    "label": "En validación; no usar dinero real",
                    "score": min(evidence_score, 84), "real_money_enabled": False}
        if not scan_results:
            next_step = {"code": "RUN_SCAN", "label": "Ejecutar un escaneo con datos vigentes",
                         "detail": "Sin una muestra actual no se puede aprobar la calidad de datos."}
        elif not quality["approved"]:
            next_step = {"code": "DATA_QUALITY", "label": "Elevar la calidad de datos a 95% o más",
                         "detail": "Todas las observaciones usadas por una señal deben superar el umbral."}
        elif sessions < MIN_SESSIONS:
            next_step = {"code": "SESSIONS", "label": f"Completar {MIN_SESSIONS} sesiones de mercado",
                         "detail": f"Faltan {MIN_SESSIONS - sessions} sesiones prospectivas."}
        elif signals < MIN_SIGNALS:
            next_step = {"code": "SIGNALS", "label": f"Reunir {MIN_SIGNALS} señales elegibles",
                         "detail": f"Faltan {MIN_SIGNALS - signals} señales auditables."}
        elif executable < MIN_EXECUTABLE_SIGNALS:
            next_step = {"code": "EXECUTABLE", "label": f"Reunir {MIN_EXECUTABLE_SIGNALS} señales ejecutables",
                         "detail": f"Faltan {MIN_EXECUTABLE_SIGNALS - executable} observaciones."}
        else:
            next_step = {"code": "PAPER_GATES", "label": "Cerrar los controles restantes de paper trading",
                         "detail": "Validar disponibilidad, desviación, valor esperado, drawdown y kill switch."}

    return {
        "technical": {"completed": 12, "total": 12, "label": "Implementación técnica terminada"},
        "current_phase": phase,
        "solidity": solidity,
        "evidence": evidence,
        "next_step": next_step,
        "release_decision": release_gate.get("decision", "RESEARCH_AND_PAPER_ONLY"),
        "notice": "La solidez aumenta sólo al cumplir evidencia; el tiempo por sí solo no aprueba una fase.",
    }
