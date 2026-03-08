"""
Nosodes extractor (pages 220-223, Table 3).
Numbered list of nosodes with Latin/Russian names and category codes.
OCR format: three-line entries (number → Latin name → Russian name).
Pure regex parsing — no LLM.
"""
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

# Lines to skip (table headers, page markers)
SKIP_KEYWORDS = [
    "Продолжение", "Окончание", "Кодовый", "Наименование",
    "Список этиологических", "Таблица 3",
]


class NosodesExtractor(BaseExtractor):
    START_PAGE = 220
    END_PAGE = 223

    def extract(self) -> dict:
        print("\n=== Nosodes (pages 220-223, Table 3) ===")

        # 1. Fetch pages
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)
        page_texts: list[tuple[int, str]] = []
        for p in pages:
            text = self.strip_headers(p["plain_text"] or "")
            if text:
                page_texts.append((p["page_num"], text))

        full_text = "\n".join(t for _, t in page_texts)

        # 2. Trim to start from Table 3
        marker = full_text.find("Список этиологических нозодов")
        if marker < 0:
            marker = full_text.find("Таблица 3")
        if marker > 0:
            full_text = full_text[marker:]

        # 3. Parse with regex
        entries = self._parse_entries(full_text)
        print(f"  Parsed {len(entries)} entries via regex")

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

    def _parse_entries(self, text: str) -> list[dict]:
        """Parse nosode entries from alternating Latin → Russian line pairs.

        Note: strip_headers() removes standalone numbers (page numbers),
        which also removes entry numbers. So we work with numberless pairs
        and auto-increment the number.
        """
        entries: list[dict] = []
        current_category = None
        lines = text.split("\n")
        number = 0

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Skip table headers
            if any(line.startswith(kw) for kw in SKIP_KEYWORDS):
                i += 1
                continue

            # Skip footnotes (start with *)
            if line.startswith("*"):
                i += 1
                continue

            # Detect category header (standalone letter or category description)
            cat = self._detect_category(line)
            if cat:
                current_category = cat
                i += 1
                continue

            # Latin line → this is a nosode entry
            if re.match(r'^[A-Za-z(]', line):
                number += 1
                name_lat = self._clean_latin(line)
                name_rus = ""

                # Look ahead for Russian name on next non-empty line
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1

                if j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and re.match(r'^[А-ЯЁа-яё(«]', next_line):
                        # Make sure it's not a category header
                        if not self._detect_category(next_line):
                            name_rus = next_line.rstrip(".,;:")
                            j += 1

                entries.append({
                    "number": number,
                    "name_lat": name_lat,
                    "name_rus": name_rus,
                    "category": current_category,
                })
                i = j
                continue

            # Skip other unrecognized lines
            i += 1

        return entries

    def _detect_category(self, line: str) -> str | None:
        """Detect category from line. Returns category key or None."""
        stripped = line.strip()
        cyrillic_to_latin = {"А": "A", "В": "B", "С": "C", "Е": "E"}

        # Single letter on a line: "А", "B", "С", "D", "E", "F"
        if len(stripped) == 1:
            letter = stripped.upper()
            if letter in cyrillic_to_latin.values() or letter in "ABCDEF":
                return CATEGORY_MAP.get(letter)
            if stripped in cyrillic_to_latin:
                return CATEGORY_MAP.get(cyrillic_to_latin[stripped])

        # "A  Нозоды коков", "D  Нозоды вирусов"
        m = re.match(r'^([A-FА-Е])\s+Нозод', stripped, re.IGNORECASE)
        if m:
            letter = m.group(1).upper()
            if letter in cyrillic_to_latin:
                letter = cyrillic_to_latin[letter]
            return CATEGORY_MAP.get(letter)

        # Category description without letter prefix — collapse spaces for OCR
        lower = stripped.lower()
        collapsed = re.sub(r'\s+', '', lower)  # "ви русов" → "вирусов"

        if "нозод" in collapsed and "коков" in collapsed:
            return "bacteria_cocci"
        if "нозод" in collapsed and "палоч" in collapsed:
            return "bacteria_bacilli"
        if "нозод" in collapsed and ("простейш" in collapsed or "гельминт" in collapsed or "микоз" in collapsed or "риккетс" in collapsed):
            return "protozoa_helminths_fungi"
        if "нозод" in collapsed and "вирус" in collapsed:
            return "virus"
        if "токсическ" in collapsed:
            return "toxic_compounds"
        if "радионуклид" in collapsed:
            return "radionuclides"

        return None

    @staticmethod
    def _clean_latin(name: str) -> str:
        """Clean up Latin name from OCR artifacts."""
        name = name.strip().rstrip(".,;:-")
        # Fix common OCR substitutions
        name = name.replace("q", "g").replace("Q", "G") if "q" in name.lower() else name
        # But preserve legitimate 'q' in words like "Seqment"... actually "q" → "g" is the right fix
        # for this OCR: "Asperqillus" → "Aspergillus", "Adenoqrippe" → "Adenogrippe"
        name = re.sub(r"q(?=[a-z])", "g", name)
        name = re.sub(r"Q(?=[a-z])", "G", name)
        # Fix "**" markers
        name = name.replace("**", "").strip()
        # Collapse spaces
        name = re.sub(r"\s+", " ", name).strip()
        return name
