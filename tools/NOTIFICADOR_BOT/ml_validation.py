"""Contratos de validación temporal y aprobación para Inversiones IA 3.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

import numpy as np


REQUIRED_PHASE5_METRICS = {
    "pr_auc", "prevalence", "precision_top_10", "benchmark_precision_top_10",
    "brier_score", "prevalence_brier", "ece", "profitable_folds_ratio",
    "worst_fold_risk_multiple", "eligible_model_usage_ratio", "reproducible",
}


@dataclass(frozen=True)
class PurgedWalkForwardSplit:
    """Partición expansiva con purga y embargo expresados en sesiones."""

    n_splits: int = 4
    purge: int = 20
    embargo: int = 5
    min_train_size: int = 100

    def split(self, sample_count: int) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        if sample_count <= self.min_train_size + self.purge + self.embargo:
            raise ValueError("No hay muestras suficientes para walk-forward purgado")
        available = sample_count - self.min_train_size - self.purge - self.embargo
        test_size = max(1, available // self.n_splits)
        for fold in range(self.n_splits):
            test_start = self.min_train_size + self.purge + fold * test_size
            test_end = sample_count if fold == self.n_splits - 1 else min(sample_count, test_start + test_size)
            train_end = test_start - self.purge
            if train_end < self.min_train_size or test_start >= test_end:
                continue
            train = np.arange(0, train_end, dtype=int)
            test = np.arange(test_start, test_end, dtype=int)
            # El embargo queda fuera del siguiente entrenamiento por la ventana expansiva.
            if fold and len(train):
                previous_test_end = self.min_train_size + self.purge + fold * test_size
                train = train[train < max(0, previous_test_end - self.embargo)]
            yield train, test


def expected_calibration_error(y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    probabilities = np.asarray(probabilities, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for index in range(bins):
        upper_inclusive = index == bins - 1
        mask = (probabilities >= edges[index]) & (
            probabilities <= edges[index + 1] if upper_inclusive else probabilities < edges[index + 1]
        )
        if np.any(mask):
            ece += float(np.mean(mask)) * abs(float(np.mean(y_true[mask])) - float(np.mean(probabilities[mask])))
    return ece


def phase5_approval(metrics: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_PHASE5_METRICS.difference(metrics))
    checks = {
        "pr_auc": not missing and metrics["pr_auc"] >= metrics["prevalence"] + 0.10,
        "precision_top_10": not missing and metrics["precision_top_10"] >= 0.55
        and metrics["precision_top_10"] >= metrics["benchmark_precision_top_10"] + 0.10,
        "brier": not missing and metrics["brier_score"] <= metrics["prevalence_brier"] * 0.90,
        "ece": not missing and metrics["ece"] <= 0.05,
        "profitable_folds": not missing and metrics["profitable_folds_ratio"] >= 0.70,
        "worst_fold": not missing and metrics["worst_fold_risk_multiple"] >= -1.50,
        "integration": not missing and metrics["eligible_model_usage_ratio"] >= 0.95,
        "reproducibility": not missing and bool(metrics["reproducible"]),
    }
    approved = not missing and all(checks.values())
    return {"approved": approved, "missing_metrics": missing, "checks": checks}


@dataclass(frozen=True)
class OODProfile:
    lower: np.ndarray
    upper: np.ndarray

    @classmethod
    def from_training(cls, features: np.ndarray) -> "OODProfile":
        data = np.asarray(features, dtype=float)
        return cls(np.nanpercentile(data, 0.5, axis=0), np.nanpercentile(data, 99.5, axis=0))

    def detect(self, feature_vector: np.ndarray) -> tuple[bool, list[int]]:
        vector = np.asarray(feature_vector, dtype=float)
        bad = np.where(~np.isfinite(vector) | (vector < self.lower) | (vector > self.upper))[0].tolist()
        return bool(bad), bad


def audit_legacy_artifact(metrics: dict[str, Any], reconstructed_samples: int) -> dict[str, Any]:
    """Aplica la regla de decisión sin acreditar métricas no reproducibles."""
    claimed = int(metrics.get("samples_total") or 0)
    approval = phase5_approval(metrics)
    provenance_ok = claimed > 0 and reconstructed_samples == claimed
    reasons = []
    if not provenance_ok:
        reasons.append(f"dataset_no_reproducible: declaradas={claimed}, reconstruidas={reconstructed_samples}")
    if approval["missing_metrics"]:
        reasons.append("faltan_metricas_fase5: " + ",".join(approval["missing_metrics"]))
    return {
        "approved_for_production": bool(provenance_ok and approval["approved"]),
        "artifact_claimed_samples": claimed,
        "reconstructed_samples": reconstructed_samples,
        "approval": approval,
        "reasons": reasons,
        "decision": "production" if provenance_ok and approval["approved"] else "experiment_only",
    }
