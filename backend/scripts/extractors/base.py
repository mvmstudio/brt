"""
Base extractor with shared logic: SQLite reads, OCR normalization, debug output.
No external LLM dependencies — all parsing is deterministic.
"""
import json
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# Deterministic OCR fixes for common misreads in Latin remedy names
OCR_FIXES: dict[str, str] = {
    # Capital I vs lowercase l confusion
    "lodum": "Iodum",
    "lris": "Iris",
    "lgnatia": "Ignatia",
    # Hyphenation artifacts
    "Lycopodi- urn": "Lycopodium",
    "Lycopodi-urn": "Lycopodium",
    "Lycopodi- um": "Lycopodium",
    "Lycopodi-um": "Lycopodium",
    # OCR letter substitutions
    "Mezereunr": "Mezereum",
    "Mezereunn": "Mezereum",
    "Stafysagria": "Staphysagria",
    "Staphisagria": "Staphysagria",
    "Stramoniuni": "Stramonium",
    "Stramoniurn": "Stramonium",
    # Cyrillic→Latin confusion
    "Allium сера": "Allium cepa",
    "Сера": "Sulfur",
    "Sulphur": "Sulfur",
    # Common remedy misspellings from OCR
    "Bryonla": "Bryonia",
    "Belladona": "Belladonna",
    "Calсarea": "Calcarea",
    "Cаlcarea": "Calcarea",
    "Nux vomlca": "Nux vomica",
    "Nux vomiса": "Nux vomica",
    "Arsenicum аlbum": "Arsenicum album",
    "Phosphonis": "Phosphorus",
    "Phosphorus": "Phosphorus",
    "Caustlcum": "Causticum",
    "Mercunus": "Mercurius",
    "Рulsatilla": "Pulsatilla",
    "Тhuja": "Thuja",
    "Нepar sulphuris": "Hepar sulphuris",
    "Lасhesis": "Lachesis",
    "Chamomila": "Chamomilla",
    "Сhamomilla": "Chamomilla",
    "Gelsemiuni": "Gelsemium",
    "Gelserniurn": "Gelsemium",
    "Gelserniurn": "Gelsemium",
    "Siliсea": "Silicea",
    "Natrum muriaticum": "Natrium muriaticum",
    "Natrum mur.": "Natrium muriaticum",
    "Nat. mur.": "Natrium muriaticum",
    "Ferrum phos.": "Ferrum phosphoricum",
    "Calc. carb.": "Calcarea carbonica",
    "Kali bichrom.": "Kali bichromicum",
    "Kali carb.": "Kali carbonicum",
    "Aurum met.": "Aurum metallicum",
    "Arg. nitr.": "Argentum nitricum",
    "Merc. sol.": "Mercurius solubilis",
}

# Build a regex for fast matching — sort by length descending so longer matches first
_OCR_FIXES_PATTERN = re.compile(
    "|".join(re.escape(k) for k in sorted(OCR_FIXES.keys(), key=len, reverse=True))
)


def normalize_remedy_name(name: str) -> str:
    """
    Normalize a remedy name: apply OCR fixes, fix casing, strip extra whitespace.
    Returns the canonical form.
    """
    if not name:
        return name

    # Apply OCR fixes
    result = _OCR_FIXES_PATTERN.sub(lambda m: OCR_FIXES[m.group(0)], name)

    # Collapse multiple spaces
    result = re.sub(r"\s+", " ", result).strip()

    # Remove trailing punctuation artifacts
    result = result.rstrip(".,;:-")

    return result


def normalize_latin_upper(name: str) -> str:
    """Normalize an ALL-CAPS Latin name to Title Case for matching."""
    if not name:
        return name
    # "ACONITUM" → "Aconitum", "NUX VOMICA" → "Nux vomica"
    parts = name.strip().split()
    if not parts:
        return name
    result = parts[0].capitalize()
    if len(parts) > 1:
        result += " " + " ".join(p.lower() for p in parts[1:])
    return normalize_remedy_name(result)


class BaseExtractor(ABC):
    """Base class for all handbook data extractors."""

    # Common page header patterns to strip from OCR text
    HEADER_PATTERNS = [
        r"^Г\.?\s*А\.?\s*Юсупов\s*$",
        r"^Энергоинформационная\s+медицина\s*$",
        r"^Раздел\s*[IІ!1]{1,2}\.?\s*ПРАКТИКА\s*$",
        r"^Раздел\s*!!\.?\s*ПРАКТИКА\s*$",
        r"^\d+\s*$",  # standalone page numbers
    ]

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.debug_dir = Path(db_path).parent / "extraction_debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    def fetch_pages(self, start: int, end: int) -> list[dict]:
        """Read pages from SQLite (sync, script is one-shot)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT page_num, render_mode, plain_text, html_content "
            "FROM pages WHERE page_num BETWEEN ? AND ? ORDER BY page_num",
            (start, end),
        )
        pages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return pages

    def strip_headers(self, text: str) -> str:
        """Remove common page headers/footers from OCR text."""
        if not text:
            return ""
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if any(re.match(p, stripped, re.IGNORECASE) for p in self.HEADER_PATTERNS):
                continue
            cleaned.append(line)
        result = "\n".join(cleaned).strip()
        return result

    def save_debug(self, name: str, data: Any) -> None:
        """Save debug JSON to extraction_debug/ directory."""
        path = self.debug_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Debug saved: {path}")

    def get_db_connection(self) -> sqlite3.Connection:
        """Get a sync SQLite connection for writes."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @abstractmethod
    def extract(self) -> dict:
        """Run extraction. Returns stats dict like {'records': 142}."""
        ...

    def preview(self, conn: sqlite3.Connection, table: str, limit: int = 3) -> None:
        """Print first N records from a table for verification."""
        cursor = conn.execute(f"SELECT * FROM {table} LIMIT ?", (limit,))
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        print(f"\n  Preview ({table}, first {limit}):")
        for row in rows:
            record = dict(zip(cols, row))
            for k, v in record.items():
                if isinstance(v, str) and len(v) > 120:
                    record[k] = v[:120] + "..."
            print(f"    {record}")
