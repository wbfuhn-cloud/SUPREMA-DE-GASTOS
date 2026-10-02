"""Gate final de liberación: fase de cierre posterior a las fases 0–11."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable


REQUIRED_PHASES = tuple(range(12))
EVIDENCE_REQUIRED = ("data_report", "validation_report", "active_comparison",
                     "human_review", "rollback_plan", "review_expiry", "artifact_hash")


def final_release_gate(phase_approvals: dict[int, bool], evidence: dict[str, Any],
                       *, critical_high_vulnerabilities: int | None,
                       real_money_requested: bool = False) -> dict[str, Any]:
    phase_checks = {f"phase_{phase}": phase_approvals.get(phase) is True for phase in REQUIRED_PHASES}
    evidence_checks = {name: bool(evidence.get(name)) for name in EVIDENCE_REQUIRED}
    security_passed = critical_high_vulnerabilities == 0
    failed = [name for name, passed in {**phase_checks, **evidence_checks,
                                        "security_scan_clean": security_passed}.items() if not passed]
    approved = not failed
    return {
        "approved_for_production": approved,
        "real_money_enabled": approved and real_money_requested,
        "decision": "PRODUCTION_APPROVED" if approved else "RESEARCH_AND_PAPER_ONLY",
        "phase_checks": phase_checks,
        "evidence_checks": evidence_checks,
        "security_scan_clean": security_passed,
        "failed": failed,
        "next_action": "human_release_authorization" if approved else "complete_failed_gates",
    }


def artifact_manifest(files: Iterable[tuple[str, bytes]], version: str) -> dict[str, Any]:
    artifacts = []
    for name, content in sorted(files):
        artifacts.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    canonical = json.dumps(artifacts, sort_keys=True, separators=(",", ":"))
    return {"version": version, "artifacts": artifacts,
            "manifest_sha256": hashlib.sha256(canonical.encode()).hexdigest()}


def rollback_decision(current_health: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    reasons = []
    if float(current_health.get("error_rate", 0)) > float(thresholds["max_error_rate"]):
        reasons.append("ERROR_RATE")
    if float(current_health.get("latency_p95_ms", 0)) > float(thresholds["max_latency_p95_ms"]):
        reasons.append("LATENCY")
    if float(current_health.get("stale_data_rate", 0)) > float(thresholds["max_stale_data_rate"]):
        reasons.append("STALE_DATA")
    return {"rollback": bool(reasons), "reasons": reasons,
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}


def current_project_gate() -> dict[str, Any]:
    """Estado honesto del proyecto después de implementar todas las fases."""
    phase_approvals = {phase: phase in {0, 1, 2, 3, 4, 7} for phase in REQUIRED_PHASES}
    evidence = {
        "data_report": True,
        "validation_report": True,
        "active_comparison": False,
        "human_review": False,
        "rollback_plan": True,
        "review_expiry": False,
        "artifact_hash": True,
    }
    result = final_release_gate(phase_approvals, evidence, critical_high_vulnerabilities=None)
    result["note"] = ("La implementación técnica 0–11 terminó, pero ML, Fourier, backtest, "
                      "paper trading, UX empírica y operación todavía requieren evidencia de pase.")
    return result
