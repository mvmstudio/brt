#!/usr/bin/env python3
"""
Rebuild handbook_fts index from existing handbook data.
Does NOT re-extract from PDF — just rebuilds the FTS virtual table.

Usage:
    cd backend
    python scripts/rebuild_fts.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings


def rebuild_fts(db_path: str) -> int:
    conn = sqlite3.connect(db_path)

    # Drop and recreate with correct schema (including entity_id)
    conn.execute("DROP TABLE IF EXISTS handbook_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE handbook_fts USING fts5(
            type,
            name,
            content,
            entity_id UNINDEXED,
            tokenize='unicode61'
        )
    """)

    count = 0

    # Remedies
    for row in conn.execute("SELECT id, name_lat, name_rus, summary FROM remedies"):
        content = f"{row[2] or ''} {row[3] or ''}"
        conn.execute(
            "INSERT INTO handbook_fts (type, name, content, entity_id) VALUES (?, ?, ?, ?)",
            ("remedy", row[1], content, row[0]),
        )
        count += 1

    # Remedy symptoms
    for row in conn.execute(
        "SELECT r.id, r.name_lat, rs.system_name, rs.description "
        "FROM remedy_symptoms rs JOIN remedies r ON r.id = rs.remedy_id"
    ):
        conn.execute(
            "INSERT INTO handbook_fts (type, name, content, entity_id) VALUES (?, ?, ?, ?)",
            ("remedy_symptom", f"{row[1]} — {row[2]}", row[3], row[0]),
        )
        count += 1

    # Therapeutic index
    for row in conn.execute("SELECT id, condition_name, remedies_list FROM therapeutic_index"):
        conn.execute(
            "INSERT INTO handbook_fts (type, name, content, entity_id) VALUES (?, ?, ?, ?)",
            ("condition", row[1], row[2], row[0]),
        )
        count += 1

    # Nosodes
    for row in conn.execute("SELECT id, name_lat, name_rus, category FROM nosodes"):
        conn.execute(
            "INSERT INTO handbook_fts (type, name, content, entity_id) VALUES (?, ?, ?, ?)",
            ("nosode", row[1], f"{row[2] or ''} {row[3] or ''}", row[0]),
        )
        count += 1

    # Etiology
    for row in conn.execute("SELECT id, disease_system, agent_name, agent_name_rus FROM etiology"):
        conn.execute(
            "INSERT INTO handbook_fts (type, name, content, entity_id) VALUES (?, ?, ?, ?)",
            ("etiology", row[2], f"{row[1]} {row[3] or ''}", row[0]),
        )
        count += 1

    # Organ preparations
    for row in conn.execute(
        "SELECT id, organ_name, organ_name_lat, disease_category FROM organ_preparations"
    ):
        conn.execute(
            "INSERT INTO handbook_fts (type, name, content, entity_id) VALUES (?, ?, ?, ?)",
            ("organ", row[1], f"{row[2] or ''} {row[3] or ''}", row[0]),
        )
        count += 1

    conn.commit()

    # Report
    print(f"handbook_fts rebuilt: {count} records")
    for row in conn.execute(
        "SELECT type, COUNT(*) FROM handbook_fts GROUP BY type ORDER BY type"
    ):
        print(f"  {row[0]}: {row[1]}")

    conn.close()
    return count


if __name__ == "__main__":
    db_path = str(Path(__file__).resolve().parent.parent / settings.database_path)
    print(f"Database: {db_path}")

    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    rebuild_fts(db_path)
