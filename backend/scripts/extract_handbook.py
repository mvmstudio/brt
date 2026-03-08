#!/usr/bin/env python3
"""
Handbook data extraction orchestrator.
Extracts structured data from OCR text in SQLite → new handbook tables.
Pure regex/deterministic parsing — no external LLM required.

Usage:
    cd backend
    python scripts/extract_handbook.py [--section NAME]

Sections: therapeutic_index, materia_medica, nosodes, etiology, organ_preparations, all
Default: all
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from scripts.extractors import (
    TherapeuticIndexExtractor,
    MateriaMedicaExtractor,
    NosodesExtractor,
    EtiologyExtractor,
    OrganPreparationsExtractor,
)

# Handbook tables to drop/recreate (order matters for foreign keys)
HANDBOOK_TABLES = [
    "handbook_fts",
    "remedy_symptoms",
    "remedies",
    "therapeutic_index",
    "nosodes",
    "etiology",
    "organ_preparations",
]

# Schema for handbook tables (same as in connection.py but for sync sqlite3)
HANDBOOK_SCHEMA = """
    CREATE TABLE IF NOT EXISTS remedies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name_lat TEXT NOT NULL UNIQUE,
        name_rus TEXT,
        source_pages TEXT,
        summary TEXT
    );

    CREATE TABLE IF NOT EXISTS remedy_symptoms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        remedy_id INTEGER NOT NULL REFERENCES remedies(id) ON DELETE CASCADE,
        system TEXT NOT NULL,
        system_name TEXT NOT NULL,
        description TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS therapeutic_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        condition_name TEXT NOT NULL,
        remedies_list TEXT NOT NULL,
        source_page INTEGER
    );

    CREATE TABLE IF NOT EXISTS nosodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number INTEGER,
        name_lat TEXT NOT NULL,
        name_rus TEXT,
        category TEXT,
        source_page INTEGER
    );

    CREATE TABLE IF NOT EXISTS etiology (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disease_system TEXT NOT NULL,
        agent_type TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        agent_name_rus TEXT,
        source_page INTEGER
    );

    CREATE TABLE IF NOT EXISTS organ_preparations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disease_category TEXT,
        organ_name TEXT NOT NULL,
        organ_name_lat TEXT,
        manufacturer TEXT,
        source_page INTEGER
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS handbook_fts USING fts5(
        type,
        name,
        content,
        entity_id UNINDEXED,
        tokenize='unicode61'
    );
"""


def reset_tables(db_path: str) -> None:
    """Drop and recreate all handbook tables. Existing tables (pages, toc, etc.) untouched."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")

    print("Resetting handbook tables...")
    for table in HANDBOOK_TABLES:
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        except sqlite3.OperationalError:
            pass  # FTS virtual tables may need special handling
    conn.commit()

    conn.executescript(HANDBOOK_SCHEMA)
    conn.commit()
    conn.close()
    print("  Tables recreated.")


def populate_fts(db_path: str) -> int:
    """Fill handbook_fts with data from all handbook tables."""
    conn = sqlite3.connect(db_path)

    # Clear FTS
    conn.execute("DELETE FROM handbook_fts")

    count = 0

    # Remedies
    for row in conn.execute("SELECT id, name_lat, name_rus, summary FROM remedies"):
        content = f"{row[2] or ''} {row[3] or ''}"
        conn.execute(
            "INSERT INTO handbook_fts (type, name, content, entity_id) VALUES (?, ?, ?, ?)",
            ("remedy", row[1], content, row[0]),
        )
        count += 1

    # Remedy symptoms (entity_id → remedy_id for navigation)
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
    conn.close()
    return count


def print_report(db_path: str) -> None:
    """Print final extraction report."""
    conn = sqlite3.connect(db_path)
    tables = {
        "therapeutic_index": "SELECT COUNT(*) FROM therapeutic_index",
        "remedies": "SELECT COUNT(*) FROM remedies",
        "remedy_symptoms": "SELECT COUNT(*) FROM remedy_symptoms",
        "nosodes": "SELECT COUNT(*) FROM nosodes",
        "etiology": "SELECT COUNT(*) FROM etiology",
        "organ_preparations": "SELECT COUNT(*) FROM organ_preparations",
        "handbook_fts": "SELECT COUNT(*) FROM handbook_fts",
    }

    print("\n" + "=" * 50)
    print("=== Extraction Complete ===")
    print("=" * 50)

    total = 0
    for name, query in tables.items():
        try:
            count = conn.execute(query).fetchone()[0]
        except sqlite3.OperationalError:
            count = 0
        print(f"  {name}: {count} records")
        total += count

    print(f"\n  Total: {total} records")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Extract handbook data from book OCR text")
    parser.add_argument(
        "--section",
        choices=["therapeutic_index", "materia_medica", "nosodes", "etiology", "organ_preparations", "all"],
        default="all",
        help="Which section to extract (default: all)",
    )
    args = parser.parse_args()

    db_path = str(Path(__file__).resolve().parent.parent / settings.database_path)
    print(f"Database: {db_path}")

    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    start_time = time.time()

    # Reset tables
    reset_tables(db_path)

    # Define extractors (no LLM client needed — all parsing is deterministic)
    extractors = {
        "therapeutic_index": lambda: TherapeuticIndexExtractor(db_path),
        "etiology": lambda: EtiologyExtractor(db_path),
        "nosodes": lambda: NosodesExtractor(db_path),
        "materia_medica": lambda: MateriaMedicaExtractor(db_path),
        "organ_preparations": lambda: OrganPreparationsExtractor(db_path),
    }

    # Run selected extractors
    results = {}
    sections = list(extractors.keys()) if args.section == "all" else [args.section]

    for section in sections:
        try:
            extractor = extractors[section]()
            result = extractor.extract()
            results[section] = result
        except Exception as e:
            print(f"\n  ERROR in {section}: {e}")
            import traceback
            traceback.print_exc()
            results[section] = {"error": str(e)}

    # Populate FTS
    print("\n=== Populating FTS index ===")
    fts_count = populate_fts(db_path)
    print(f"  handbook_fts: {fts_count} records")

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s")

    # Final report
    print_report(db_path)


if __name__ == "__main__":
    main()
