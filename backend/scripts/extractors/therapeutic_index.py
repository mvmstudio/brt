"""
Therapeutic Index extractor (pages 180-203).
Pattern: disease name (cyrillic line) followed by comma-separated Latin remedy names.
"""
import json
import re

from .base import BaseExtractor


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

        # 4. LLM verification to fix OCR artifacts in remedy names
        entries = self._verify_with_llm(entries)

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

    def _verify_with_llm(self, entries: list[dict]) -> list[dict]:
        """Use LLM to verify and fix OCR artifacts in the parsed data."""
        print("  Verifying with LLM...")

        # Build concise representation for LLM
        compact = []
        for e in entries:
            compact.append({
                "c": e["condition"],
                "r": e["remedies"][:5],  # first 5 for context
                "n": len(e["remedies"]),
            })

        system_prompt = """You are a homeopathic medicine expert verifying OCR-extracted data.
You will receive a list of conditions with sample remedies from a therapeutic index.

Your task:
1. Fix obvious OCR errors in condition names (e.g., "Аденоиды" is correct, "Аденонды" would be a typo)
2. Fix obvious OCR errors in remedy names (e.g., "Belladonna" not "Belladoma")
3. Identify entries that seem to be continuation of previous entries (not new conditions)
4. DO NOT add new entries or remedies — only fix existing OCR artifacts

Return JSON: {"fixes": [{"index": 0, "condition_fixed": "...", "note": "..."}], "merge": [{"from": 5, "into": 4, "note": "continuation"}]}
If no fixes needed, return {"fixes": [], "merge": []}"""

        user_prompt = json.dumps(compact, ensure_ascii=False)

        try:
            result = self.llm_call(system_prompt, user_prompt, max_tokens=4096)
            data = json.loads(result)

            # Apply fixes
            fixes_applied = 0
            for fix in data.get("fixes", []):
                idx = fix["index"]
                if 0 <= idx < len(entries) and "condition_fixed" in fix:
                    old = entries[idx]["condition"]
                    entries[idx]["condition"] = fix["condition_fixed"]
                    print(f"    Fixed: '{old}' -> '{fix['condition_fixed']}'")
                    fixes_applied += 1

            # Apply merges (reverse order to preserve indices)
            merges = sorted(data.get("merge", []), key=lambda m: m["from"], reverse=True)
            for merge in merges:
                from_idx = merge["from"]
                into_idx = merge["into"]
                if 0 <= from_idx < len(entries) and 0 <= into_idx < len(entries):
                    entries[into_idx]["remedies"].extend(entries[from_idx]["remedies"])
                    entries.pop(from_idx)
                    print(f"    Merged entry {from_idx} into {into_idx}")
                    fixes_applied += 1

            print(f"  LLM verification: {fixes_applied} fixes applied")

        except Exception as e:
            print(f"  LLM verification failed ({e}), using raw parsed data")

        return entries
