"""
Extract Table of Contents from PDF pages 4-6.
Parses the TOC text and stores structured entries in SQLite.
"""
import sys
import os
import re
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymupdf
import aiosqlite
from pathlib import Path

from app.config import settings

PDF_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", settings.pdf_path)
)
DB_PATH = Path(os.path.dirname(__file__)).parent / settings.data_dir / "brt.db"


def parse_toc_from_pdf(pdf_path: str) -> list[dict]:
    """Extract TOC entries from pages 4-6 of the PDF."""
    doc = pymupdf.open(pdf_path)
    toc_text = ""
    for page_idx in [3, 4, 5]:  # pages 4, 5, 6 (0-indexed)
        toc_text += doc[page_idx].get_text() + "\n"
    doc.close()

    entries = []
    sort_order = 0

    for line in toc_text.split("\n"):
        line = line.strip()
        if not line or line == "ОГЛАВЛЕНИЕ" or line == "Оглавление":
            continue

        # Extract page number from end of line (after dots or spaces)
        match = re.search(r'[.\s]+(\d{1,3})\s*$', line)
        if not match:
            continue

        page_num = int(match.group(1))
        title = line[:match.start()].strip().rstrip('.')

        if not title:
            continue

        # Determine level from formatting
        level = determine_level(title)

        entries.append({
            "level": level,
            "title": title,
            "page_num": page_num,
            "sort_order": sort_order,
        })
        sort_order += 1

    return entries


def determine_level(title: str) -> int:
    """Determine TOC entry level based on title format."""
    # Level 0: Раздел I, Раздел II
    if re.match(r'^Раздел\s+[IVX]+\.', title):
        return 0
    # Level 1: ГЛАВА, ПРЕДИСЛОВИЕ, ВВЕДЕНИЕ, ЗАКЛЮЧЕНИЕ, ПРИЛОЖЕНИЕ
    if re.match(r'^(ГЛАВА|ПРЕДИСЛОВИЕ|ВВЕДЕНИЕ|ЗАКЛЮЧЕНИЕ|ПРИЛОЖЕНИЕ|ЛИТЕРАТУРА)', title):
        return 1
    # Level 2: numbered sections like 1.1., 2.1., etc.
    if re.match(r'^\d+\.\d+\.', title):
        return 2
    # Level 3: deeper numbered sections like 4.2.1., 4.2.2., etc.
    if re.match(r'^\d+\.\d+\.\d+\.', title):
        return 3
    # Default
    return 1


async def store_toc(entries: list[dict]):
    """Store TOC entries in SQLite."""
    db = await aiosqlite.connect(str(DB_PATH))

    await db.execute("DELETE FROM toc")

    # First pass: insert all entries
    parent_stack = {}  # level -> id
    for entry in entries:
        level = entry["level"]
        parent_id = parent_stack.get(level - 1)

        cursor = await db.execute(
            "INSERT INTO toc (level, title, page_num, parent_id, sort_order) VALUES (?, ?, ?, ?, ?)",
            (level, entry["title"], entry["page_num"], parent_id, entry["sort_order"]),
        )
        entry_id = cursor.lastrowid
        parent_stack[level] = entry_id
        # Clear deeper levels
        for l in list(parent_stack.keys()):
            if l > level:
                del parent_stack[l]

    # Also update chapter info in pages table
    for i, entry in enumerate(entries):
        next_page = entries[i + 1]["page_num"] if i + 1 < len(entries) else 483
        await db.execute(
            "UPDATE pages SET chapter = ?, title = COALESCE(title, ?) WHERE page_num >= ? AND page_num < ?",
            (entry["title"], entry["title"], entry["page_num"], next_page),
        )

    await db.commit()
    await db.close()
    print(f"Stored {len(entries)} TOC entries")


async def main():
    print(f"Extracting TOC from: {PDF_PATH}")
    entries = parse_toc_from_pdf(PDF_PATH)

    print(f"\nFound {len(entries)} TOC entries:")
    for e in entries:
        indent = "  " * e["level"]
        print(f"  {indent}[L{e['level']}] p.{e['page_num']:>3}: {e['title'][:80]}")

    await store_toc(entries)


if __name__ == "__main__":
    asyncio.run(main())
