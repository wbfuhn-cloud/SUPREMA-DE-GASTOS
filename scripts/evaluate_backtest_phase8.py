"""Genera el dictamen reproducible de disponibilidad para la fase 8."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


STRATEGIES = [
    "buy_hold_spy", "buy_hold_qqq", "heuristic", "ml", "heuristic_ml",
    "heuristic_ml_fourier", "without_learned_exit", "with_learned_exit",
]


def evaluation() -> dict:
    return {
        "schema": "inversiones-ia-phase8-evaluation/1.0",
        "historical_dataset_available": False,
        "historical_universe_composition_available": False,
        "verified_training_predictions_available": 0,
        "final_test_status": "UNTOUCHED",
        "strategies": {name: {"status": "NOT_EVALUATED", "reason": "missing_traceable_market_dataset"}
                       for name in STRATEGIES},
        "segmentations": {name: "NOT_EVALUATED" for name in
                          ("regime", "sector", "liquidity", "volatility", "horizon")},
        "bootstrap": "NOT_EVALUATED",
        "sensitivity": "NOT_EVALUATED",
        "multiple_testing_correction": "IMPLEMENTED_BONFERRONI_NOT_APPLIED",
        "blockers": [
            "No existe serie histórica trazable con señales y resultados verificables.",
            "No existe composición histórica del universo; usar la lista actual introduciría supervivencia.",
            "El ML de fase 5 no está aprobado y Fourier no superó ablación real.",
        ],
        "approved": False,
        "decision": "DO_NOT_ADVANCE_TO_PAPER_TRADING",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluation()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
