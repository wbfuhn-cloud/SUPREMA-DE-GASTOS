"""Genera SQL seguro para importar la base SQLite local a D1."""

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "database" / "expenses.db"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / ".generated_legacy_import"


def sql_value(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def main():
    connection = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute("SELECT * FROM expenses ORDER BY id").fetchall()
    connection.close()

    statements = []
    for row in rows:
        values = [
            row["date"], row["merchant"], row["category"],
            row["payment_method"], row["details"], row["total"],
            row["type"], row["status"], row["subcategory"] or "",
            row["project"] or "", "legacy", f"legacy:{row['id']}",
        ]
        statements.append(
            "INSERT OR IGNORE INTO expenses "
            "(date, merchant, category, payment_method, details, total, "
            "type, status, subcategory, project, source, source_id) VALUES ("
            + ", ".join(sql_value(value) for value in values)
            + ");"
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    for old_file in OUTPUT_DIR.glob("*.sql"):
        old_file.unlink()
    chunk_size = 100
    for index in range(0, len(statements), chunk_size):
        chunk = statements[index:index + chunk_size]
        output = OUTPUT_DIR / f"chunk_{index // chunk_size:03d}.sql"
        output.write_text("\n".join(chunk) + "\n", encoding="utf-8")
    print(json.dumps({"source": str(SOURCE), "output": str(OUTPUT_DIR), "rows": len(rows), "chunks": (len(statements) + chunk_size - 1) // chunk_size}))


if __name__ == "__main__":
    main()
