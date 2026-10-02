"""Contratos de transparencia de la UX de Inversiones IA 3.0."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


UX_CONTRACT_VERSION = "1.0.0"
MISSING = "N/D"


def _present(value: Any) -> Any:
    return MISSING if value is None or value == "" else value


def _uncertainty(row: dict[str, Any]) -> str:
    quality = float(row.get("Data_Quality") or 0.0)
    if quality < 0.95 or row.get("ML_OOD_Detected"):
        return "alta"
    if row.get("Calibrated_Probability") is None:
        return "no cuantificada"
    probability = float(row["Calibrated_Probability"])
    return "baja" if abs(probability - 0.5) >= 0.20 else "media"


def signal_explanation(row: dict[str, Any], generated_at_utc: str | None = None) -> dict[str, Any]:
    """Normaliza una señal sin convertir ausencias en cero ni en 50 %."""
    quote = row.get("Quote") or {}
    fusion = row.get("Fusion_Explanation") or {}
    risk = row.get("Risk_Plan") or {}
    probability = row.get("Calibrated_Probability")
    model_used = probability is not None and not row.get("ML_Degraded_Reason") and not row.get("ML_OOD_Detected")
    spectral_used = bool(row.get("Spectral_Validated", False))
    modules = {
        "heuristic": {"active": bool(row.get("Heuristic_Version")), "version": _present(row.get("Heuristic_Version"))},
        "ml": {"active": model_used, "version": _present(row.get("Model_Version")),
               "reason_inactive": None if model_used else _present(row.get("ML_Degraded_Reason") or "modelo no aprobado")},
        "fourier": {"active": spectral_used, "version": _present(row.get("Spectral_Version")),
                    "reason_inactive": None if spectral_used else "experimental; excluido del veredicto"},
    }
    missing = list(row.get("Missing_Indicators") or [])
    for field, value in (("probabilidad_ml", probability), ("precio_invalidacion", risk.get("stop_price")),
                         ("tamano_sugerido", risk.get("position_size_shares"))):
        if value is None:
            missing.append(field)
    return {
        "ux_contract_version": UX_CONTRACT_VERSION,
        "signal": _present(row.get("Signal_State")),
        "horizon": _present(risk.get("horizon") or "swing 5-20 sesiones"),
        "timestamp_utc": _present(quote.get("market_timestamp") or generated_at_utc),
        "freshness_seconds": _present(quote.get("freshness_seconds")),
        "price": _present(row.get("Price")),
        "provider": _present(quote.get("provider")),
        "calibrated_ml_probability": _present(probability),
        "heuristic_score": _present(row.get("Score")),
        "spectral_signal": _present(row.get("Spectral_Score")) if spectral_used else "EXPERIMENTAL_NO_USADA",
        "data_quality": _present(row.get("Data_Quality")),
        "uncertainty": _uncertainty(row),
        "factors_for": fusion.get("factors_for") or ["ningún factor favorable suficiente"],
        "factors_against": fusion.get("factors_against") or ["explicación no disponible"],
        "invalidation_price": _present(risk.get("stop_price")),
        "stop_price": _present(risk.get("stop_price")),
        "target_price": _present(row.get("Target_Price")),
        "suggested_size_shares": _present(risk.get("position_size_shares")),
        "model_version": _present(row.get("Model_Version")),
        "rules_version": _present(row.get("Fusion_Version")),
        "comparable_history": _present(row.get("Comparable_History")),
        "modules": modules,
        "missing_data": sorted(set(missing)),
        "disclaimer": "Análisis educativo: no garantiza resultados ni constituye asesoría financiera.",
    }


def adaptive_ai_status(*, ml_status: dict[str, Any], learner_stats: dict[str, Any],
                       paper_status: dict[str, Any]) -> dict[str, Any]:
    metrics = ml_status.get("metrics") or {}
    audit = ml_status.get("phase5_audit") or {}
    return {
        "last_training": _present(ml_status.get("last_trained")),
        "next_evaluation": "al completar la ventana prospectiva; sin reentrenar durante ella",
        "dataset": {
            "period": _present(metrics.get("dataset_period")),
            "samples": _present(metrics.get("samples_total") or audit.get("claimed_samples")),
            "positives": _present(metrics.get("positive_samples")),
            "assets": _present(metrics.get("assets")),
        },
        "out_of_sample_metrics": _present(metrics.get("out_of_sample")),
        "confusion_matrix_by_horizon": _present(metrics.get("confusion_matrix_by_horizon")),
        "calibration_curve": _present(metrics.get("calibration_curve")),
        "verified_predictions": learner_stats.get("verified", 0),
        "version_changes": _present(ml_status.get("version_changes")),
        "drift": _present(ml_status.get("drift_status")),
        "operational_state": "paper_trading" if not paper_status.get("approved") else "paper_approved",
        "modules": {
            "heuristic": "activo",
            "ml": "activo" if ml_status.get("production_approved") else "experimental_inactivo",
            "fourier": "experimental_inactivo",
        },
        "degradation_reason": _present(ml_status.get("degraded_reason") or None),
    }


def filter_history(rows: Iterable[dict[str, Any]], **filters: Any) -> list[dict[str, Any]]:
    """Aplica los seis filtros exigidos por fase 10 sin mutar el historial."""
    aliases = {"ticker": "ticker", "model": "model_version", "signal": "signal",
               "horizon": "horizon", "result": "outcome"}
    result = []
    for row in rows:
        timestamp = str(row.get("scan_date") or row.get("timestamp_utc") or "")
        if filters.get("date_from") and timestamp[:10] < str(filters["date_from"]):
            continue
        if filters.get("date_to") and timestamp[:10] > str(filters["date_to"]):
            continue
        if any(filters.get(name) and str(row.get(field, "")).lower() != str(filters[name]).lower()
               for name, field in aliases.items()):
            continue
        result.append(dict(row))
    return result
