"""
Base extractor with shared logic: SQLite reads, Groq LLM calls, rate limiting, debug output.
"""
import json
import re
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from openai import OpenAI


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

    def __init__(self, db_path: str, groq_client: OpenAI, model: str):
        self.db_path = db_path
        self.client = groq_client
        self.model = model
        self.debug_dir = Path(db_path).parent / "extraction_debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self._last_llm_call = 0.0

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
        # Remove leading/trailing blank lines
        result = "\n".join(cleaned).strip()
        return result

    def llm_call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        """Groq API call with rate limiting and retry on 429."""
        # Rate limiting: 3 sec between calls
        elapsed = time.time() - self._last_llm_call
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)

        backoff = 10.0
        for attempt in range(4):
            try:
                self._last_llm_call = time.time()
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content or "{}"
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate" in error_str.lower():
                    print(f"  Rate limited (attempt {attempt + 1}/4), waiting {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise
        raise RuntimeError("LLM call failed after 4 retries (rate limit)")

    def llm_call_text(self, system: str, user: str, max_tokens: int = 4096) -> str:
        """Groq API call returning plain text (no JSON mode)."""
        elapsed = time.time() - self._last_llm_call
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)

        backoff = 10.0
        for attempt in range(4):
            try:
                self._last_llm_call = time.time()
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate" in error_str.lower():
                    print(f"  Rate limited (attempt {attempt + 1}/4), waiting {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise
        raise RuntimeError("LLM call failed after 4 retries (rate limit)")

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
            # Truncate long values
            for k, v in record.items():
                if isinstance(v, str) and len(v) > 120:
                    record[k] = v[:120] + "..."
            print(f"    {record}")
