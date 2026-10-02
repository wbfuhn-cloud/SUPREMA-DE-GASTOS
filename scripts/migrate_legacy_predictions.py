"""Resuelve predicciones pendientes del esquema anterior sin inventar etiquetas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "NOTIFICADOR_BOT"))

from prediction_ledger import PredictionLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-db", required=True)
    parser.add_argument("--ledger-db", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    ledger = PredictionLedger(args.ledger_db)
    rows = ledger.import_legacy_as_irrecoverable(args.legacy_db)
    report = {
        "schema": "inversiones-ia-legacy-recovery/1.0",
        "source": Path(args.legacy_db).name,
        "destination": Path(args.ledger_db).name,
        "resolved_count": len(rows),
        "unexplained_pending_count": 0,
        "resolutions": rows,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"resolved": len(rows), "unexplained_pending": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
