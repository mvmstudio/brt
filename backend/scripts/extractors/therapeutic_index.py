"""
Therapeutic Index extractor (pages 180-203).
Pattern: disease name (cyrillic line) followed by comma-separated Latin remedy names.
Pure regex parsing with OCR normalization — no LLM.
"""
import json
import re

from .base import BaseExtractor, normalize_remedy_name


class TherapeuticIndexExtractor(BaseExtractor):
    START_PAGE = 180
    END_PAGE = 203

    # Marker text after which the actual index begins on page 180
    INDEX_START_MARKER = "Аденоиды"

    def extract(self) -> dict:
        print("\n=== Therapeutic Index (pages 180-203) ===")

        # 1. Fetch and concat all pages
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)
        raw_texts = []
        for p in pages:
            text = self.strip_headers(p["plain_text"] or "")
            if text:
                raw_texts.append(text)
        full_text = "\n".join(raw_texts)

        # 2. Trim everything before the index starts (intro text on page 180)
        marker_pos = full_text.find(self.INDEX_START_MARKER)
        if marker_pos > 0:
            full_text = full_text[marker_pos:]

        # 3. Parse with regex
        entries = self._parse_entries(full_text)
        print(f"  Parsed {len(entries)} entries via regex")

        # 4. Apply deterministic OCR normalization (replaces LLM verification)
        for entry in entries:
            entry["remedies"] = [normalize_remedy_name(r) for r in entry["remedies"]]
            # Remove empty entries after normalization
            entry["remedies"] = [r for r in entry["remedies"] if r and len(r) > 1]

        # 5. Save debug
        self.save_debug("therapeutic_index", entries)

        # 6. Insert into DB
        conn = self.get_db_connection()
        try:
            for entry in entries:
                conn.execute(
                    "INSERT INTO therapeutic_index (condition_name, remedies_list, source_page) "
                    "VALUES (?, ?, ?)",
                    (entry["condition"], json.dumps(entry["remedies"], ensure_ascii=False), entry.get("source_page")),
                )
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM therapeutic_index").fetchone()[0]
            print(f"  Inserted {count} records into therapeutic_index")
            self.preview(conn, "therapeutic_index")
            return {"records": count}
        finally:
            conn.close()

    def _parse_entries(self, text: str) -> list[dict]:
        """Parse condition-remedy pairs using line analysis."""
        entries = []
        lines = text.split("\n")

        current_condition = None
        current_remedies_text = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check if this is a condition name (cyrillic-dominant, short-ish, no commas at end pattern)
            if self._is_condition_name(stripped):
                # Save previous entry
                if current_condition and current_remedies_text:
                    remedies = self._parse_remedies(current_remedies_text)
                    if remedies:
                        entries.append({
                            "condition": current_condition,
                            "remedies": remedies,
                        })
                current_condition = stripped
                current_remedies_text = ""
            else:
                # Continuation of remedy list
                current_remedies_text += " " + stripped

        # Don't forget the last entry
        if current_condition and current_remedies_text:
            remedies = self._parse_remedies(current_remedies_text)
            if remedies:
                entries.append({
                    "condition": current_condition,
                    "remedies": remedies,
                })

        return entries

    def _is_condition_name(self, line: str) -> bool:
        """Heuristic: condition names are predominantly Cyrillic, often with parenthetical clarifications."""
        # Skip very short lines
        if len(line) < 3:
            return False

        # Lines that start with Latin characters are remedy continuations
        if re.match(r'^[A-Z][a-z]', line):
            return False

        # If line contains comma-separated Latin words — it's remedies
        latin_words = re.findall(r'[A-Z][a-z]+', line)
        commas = line.count(",")
        if commas >= 3 and len(latin_words) > 3:
            return False

        # Count cyrillic vs latin chars
        cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', line))
        latin = len(re.findall(r'[a-zA-Z]', line))
        total = cyrillic + latin
        if total == 0:
            return False

        # Condition names are mostly cyrillic
        return cyrillic / total > 0.5

    def _parse_remedies(self, text: str) -> list[str]:
        """Split comma-separated remedy names, clean up."""
        text = text.strip().rstrip(".")
        # Split by comma
        parts = [p.strip() for p in text.split(",")]
        remedies = []
        for part in parts:
            # Clean up: remove trailing/leading punctuation, numbers, page references
            cleaned = part.strip().strip(".,;:")
            # Skip empty or too short
            if len(cleaned) < 2:
                continue
            # Skip standalone numbers (page numbers leaked in)
            if re.match(r'^\d+$', cleaned):
                continue
            remedies.append(cleaned)
        return remedies

