"""
Nosodes extractor (pages 220-223, Table 3).
Numbered list of nosodes with Latin/Russian names and category codes.
OCR text from image pages — use LLM to structure.
"""
import json
import re

from .base import BaseExtractor

# Category mapping from book's letter codes
CATEGORY_MAP = {
    "A": "bacteria_cocci",
    "B": "bacteria_bacilli",
    "C": "protozoa_helminths_fungi",
    "D": "virus",
    "E": "toxic_compounds",
    "F": "radionuclides",
}


class NosodesExtractor(BaseExtractor):
    START_PAGE = 220
    END_PAGE = 223

    def extract(self) -> dict:
        print("\n=== Nosodes (pages 220-223, Table 3) ===")

        # 1. Fetch pages
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)
        texts = []
        for p in pages:
            text = self.strip_headers(p["plain_text"] or "")
            if text:
                texts.append(text)
        full_text = "\n".join(texts)

        # 2. Trim to start from "Список этиологических нозодов" or first numbered entry
        marker = full_text.find("Список этиологических нозодов")
        if marker > 0:
            full_text = full_text[marker:]

        # 3. Use LLM to parse the messy OCR table
        entries = self._parse_with_llm(full_text)
        print(f"  Parsed {len(entries)} entries via LLM")

        # 4. Save debug
        self.save_debug("nosodes", entries)

        # 5. Insert into DB
        conn = self.get_db_connection()
        try:
            for entry in entries:
                conn.execute(
                    "INSERT INTO nosodes (number, name_lat, name_rus, category, source_page) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (entry.get("number"), entry["name_lat"], entry.get("name_rus"),
                     entry.get("category"), entry.get("source_page")),
                )
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM nosodes").fetchone()[0]
            print(f"  Inserted {count} records into nosodes")

            # Stats by category
            cursor = conn.execute(
                "SELECT category, COUNT(*) FROM nosodes GROUP BY category ORDER BY COUNT(*) DESC"
            )
            print("  By category:")
            for row in cursor:
                print(f"    {row[0]}: {row[1]}")

            self.preview(conn, "nosodes")
            return {"records": count}
        finally:
            conn.close()

    def _parse_with_llm(self, text: str) -> list[dict]:
        """Use LLM to extract structured nosode entries from OCR table text."""
        system_prompt = """You are a medical data extraction expert. You will receive OCR text from a table of nosodes (homeopathic preparations from disease agents).

The table has these columns:
- Code number (integer, 1-166+)
- Latin name of nosode
- Russian name/description

The nosodes are grouped into categories:
- A: Нозоды кокков (bacteria cocci)
- B: Нозоды бактерий (bacteria bacilli) — starts around number 22-23
- C: Нозоды риккетсий, простейших, гельминтов, микозов (protozoa/helminths/fungi) — starts around 90
- D: Нозоды вирусов (viruses) — starts around 137
- E: Токсические соединения (toxic compounds)
- F: Радионуклиды (radionuclides)

Extract ALL numbered nosode entries. For categories E and F, they usually only appear as letter codes without individual entries, so skip them.

Return JSON:
{
  "entries": [
    {"number": 1, "name_lat": "Branhamella catarrhalis", "name_rus": "Бранхамелла катаральная", "category": "bacteria_cocci"},
    ...
  ]
}

Rules:
- Fix obvious OCR errors in Latin names (e.g., "q" might be "g", "I" might be "l")
- Keep Russian names as-is (fix only obvious OCR errors)
- Map categories: A→bacteria_cocci, B→bacteria_bacilli, C→protozoa_helminths_fungi, D→virus
- Include ALL entries (expect ~166 entries)
- If parenthetical synonyms exist, include them in name_lat"""

        result = self.llm_call(system_prompt, f"OCR table text:\n\n{text}", max_tokens=8192)

        try:
            data = json.loads(result)
            entries = data.get("entries", [])
            return entries
        except json.JSONDecodeError as e:
            print(f"  LLM returned invalid JSON: {e}")
            return []
