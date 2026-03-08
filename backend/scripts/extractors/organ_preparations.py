"""
Organ Preparations extractor (pages 262-278).
Bilingual lists: Russian organ name — Latin organ name, grouped by disease category.
Pure regex parsing — no LLM.
"""
import re

from .base import BaseExtractor


# Pattern for Latin name with dash prefix: "- Bronchi" or "-Bronchi" or "—  Bronchi"
LATIN_PREFIX_RE = re.compile(r'^\s*[-–—]\s*([A-Za-z].+)$')

# Category header: ALL CAPS Cyrillic, contains "ЗАБОЛЕВАНИ" or similar disease markers
CATEGORY_HEADER_RE = re.compile(
    r'^(ЗАБОЛЕВАНИ[ЯЕИЙ]\s+.+|'
    r'ПОРАЖЕНИ[ЕЯ]\s+.+|'
    r'СУСТАВЫ\s+.+|'
    r'ВИСОЧНО[-–]?.+|'
    r'НАРУШЕНИ[ЕЯ]\s+.+)$',
    re.IGNORECASE,
)


class OrganPreparationsExtractor(BaseExtractor):
    START_PAGE = 262
    END_PAGE = 278

    def extract(self) -> dict:
        print("\n=== Organ Preparations (pages 262-278) ===")

        # 1. Fetch all pages
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)

        # Skip intro page 262 (all prose)
        data_pages = [p for p in pages if p["plain_text"] and p["page_num"] > 262]
        print(f"  Data pages: {len(data_pages)}")

        # 2. Parse all pages with regex
        all_entries = self._parse_all_pages(data_pages)
        print(f"  Parsed {len(all_entries)} entries via regex")

        # 3. Save debug
        self.save_debug("organ_preparations", all_entries)

        # 4. Insert into DB
        conn = self.get_db_connection()
        try:
            for entry in all_entries:
                conn.execute(
                    "INSERT INTO organ_preparations (disease_category, organ_name, organ_name_lat, manufacturer, source_page) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (entry.get("disease_category"), entry["organ_name"],
                     entry.get("organ_name_lat"), entry.get("manufacturer"),
                     entry.get("source_page")),
                )
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM organ_preparations").fetchone()[0]
            print(f"  Inserted {count} records into organ_preparations")

            cursor = conn.execute(
                "SELECT disease_category, COUNT(*) FROM organ_preparations "
                "GROUP BY disease_category ORDER BY COUNT(*) DESC LIMIT 5"
            )
            print("  Top 5 categories:")
            for row in cursor:
                print(f"    {row[0]}: {row[1]}")

            self.preview(conn, "organ_preparations")
            return {"records": count}
        finally:
            conn.close()

    def _parse_all_pages(self, pages: list[dict]) -> list[dict]:
        """Parse organ preparations from all pages."""
        all_entries: list[dict] = []
        current_category = None

        for page in pages:
            text = self.strip_headers(page["plain_text"] or "")
            if not text:
                continue

            page_num = page["page_num"]
            lines = text.split("\n")

            # Collect Russian names and Latin names for this page under current category
            russian_names: list[str] = []
            latin_names: list[str] = []

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # Check for category header
                cat_match = CATEGORY_HEADER_RE.match(stripped)
                if cat_match:
                    # Flush pending pairs before changing category
                    entries = self._pair_names(russian_names, latin_names, current_category, page_num)
                    all_entries.extend(entries)
                    russian_names = []
                    latin_names = []

                    # Clean up category name
                    current_category = self._clean_category(cat_match.group(1))
                    continue

                # Check for Latin name (with dash prefix)
                latin_match = LATIN_PREFIX_RE.match(stripped)
                if latin_match:
                    lat_name = latin_match.group(1).strip().rstrip(".,;:")
                    if lat_name and len(lat_name) > 1:
                        latin_names.append(lat_name)
                    continue

                # Check for mixed line: "Russian name  - Latin name" or "Russian - Latin"
                mixed = self._try_mixed_line(stripped)
                if mixed:
                    rus, lat = mixed
                    russian_names.append(rus)
                    latin_names.append(lat)
                    continue

                # Check if it's a Russian organ name (starts with Cyrillic, no more than a few words)
                if self._is_russian_organ_name(stripped):
                    russian_names.append(stripped)
                    continue

                # Skip unrecognized lines (page numbers, headers, footnotes)

            # Flush remaining pairs for this page
            entries = self._pair_names(russian_names, latin_names, current_category, page_num)
            all_entries.extend(entries)

        return all_entries

    def _try_mixed_line(self, line: str) -> tuple[str, str] | None:
        """Try to split a line into Russian name + Latin name separated by dash."""
        # Pattern: "Бронхи - Bronchi" or "Бронхи — Bronchi"
        m = re.match(r'^([А-ЯЁа-яё][\w\s()]+?)\s+[-–—]\s*([A-Za-z].+)$', line)
        if m:
            return (m.group(1).strip(), m.group(2).strip().rstrip(".,;:"))
        return None

    def _is_russian_organ_name(self, line: str) -> bool:
        """Check if line looks like a Russian organ name (not a header, number, etc.)."""
        if not line:
            return False
        # Must start with Cyrillic
        if not re.match(r'^[А-ЯЁа-яё]', line):
            return False
        # Should not be all caps (that's a category header)
        if line == line.upper() and len(line) > 15:
            return False
        # Should not be a table header ("Продолжение таблицы", "Окончание")
        lower = line.lower()
        if any(kw in lower for kw in ["продолжение", "окончание", "таблиц", "кодовый"]):
            return False
        # Should not be too long (organ names are usually < 80 chars)
        if len(line) > 100:
            return False
        # Should not contain mostly digits
        if sum(c.isdigit() for c in line) > len(line) * 0.3:
            return False
        return True

    def _pair_names(
        self,
        russian: list[str],
        latin: list[str],
        category: str | None,
        page_num: int,
    ) -> list[dict]:
        """Pair Russian and Latin names by position. Handle mismatches gracefully."""
        entries = []
        max_len = max(len(russian), len(latin))

        for i in range(max_len):
            rus = russian[i] if i < len(russian) else None
            lat = latin[i] if i < len(latin) else None

            if rus:
                entries.append({
                    "organ_name": rus,
                    "organ_name_lat": lat or "",
                    "disease_category": category,
                    "source_page": page_num,
                })
            elif lat:
                # Latin name without Russian pair — store as-is
                entries.append({
                    "organ_name": lat,  # Use Latin as primary
                    "organ_name_lat": lat,
                    "disease_category": category,
                    "source_page": page_num,
                })

        return entries

    @staticmethod
    def _clean_category(raw: str) -> str:
        """Clean up category name from OCR artifacts."""
        # Collapse whitespace
        result = re.sub(r'\s+', ' ', raw).strip()
        # Fix common OCR issues
        result = result.replace("!!", "II").replace("!!.", "II.")
        # Title case for consistency
        if result == result.upper():
            result = result.capitalize()
            # But keep "ЗАБОЛЕВАНИЯ" format nicely
            result = re.sub(
                r'\b(органов|системы|половых|мужских|женских|верхних|нижних|'
                r'бронхолегочной|сердечно-сосудистой|мочеполовой|нервной|'
                r'опорно-двигательной|эндокринной|пищеварительной)\b',
                lambda m: m.group(0).lower(),
                result,
                flags=re.IGNORECASE,
            )
        return result
