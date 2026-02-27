"""
Organ Preparations extractor (pages 262-278).
Bilingual lists: Russian organ name — Latin organ name, grouped by disease category.
Mixed html/image pages.
"""
import json
import re

from .base import BaseExtractor


class OrganPreparationsExtractor(BaseExtractor):
    START_PAGE = 262
    END_PAGE = 278

    # Pattern for disease category headers (ALL CAPS or mixed)
    CATEGORY_RE = re.compile(
        r'^ЗАБОЛЕВАНИ[ЯЕ]\s+(.+?)$|^СУСТАВЫ\s+(.+?)$|^ВИСОЧНО[-–](.+?)$',
        re.IGNORECASE,
    )

    def extract(self) -> dict:
        print("\n=== Organ Preparations (pages 262-278) ===")

        # 1. Fetch all pages
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)

        # Filter pages with text (skip intro page 262 which is all prose)
        data_pages = [p for p in pages if p["plain_text"] and p["page_num"] > 262]
        print(f"  Data pages: {len(data_pages)}")

        # 2. Process ALL pages with LLM in batches (text layout is two-column, not parseable by regex)
        all_entries = []
        batch_size = 4
        for i in range(0, len(data_pages), batch_size):
            batch = data_pages[i:i + batch_size]
            page_nums = [p["page_num"] for p in batch]
            print(f"  Processing pages {page_nums}...")
            entries = self._parse_pages_llm(batch)
            all_entries.extend(entries)
            print(f"    Got {len(entries)} entries")

        # 4. Save debug
        self.save_debug("organ_preparations", all_entries)

        # 5. Insert into DB
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

            # Stats by category
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

    def _parse_pages_llm(self, pages: list[dict]) -> list[dict]:
        """Use LLM to parse organ preparations from OCR text (both html and image pages)."""
        texts = []
        for p in pages:
            text = self.strip_headers(p["plain_text"] or "")
            if text:
                texts.append(f"--- Page {p['page_num']} ---\n{text}")

        full_text = "\n".join(texts)
        if not full_text.strip():
            return []

        system_prompt = """You are a medical data extraction expert. You will receive OCR text from pages listing potentiated organ preparations (потенцированные органные препараты).

The text layout is two-column: Russian organ names on the left, Latin organ names on the right, separated by dashes (- or —). They are grouped under disease category headers (ЗАБОЛЕВАНИЯ ..., СУСТАВЫ ..., etc.).

IMPORTANT: The two columns may appear mixed in the OCR text. Russian names and Latin names alternate or are in separate blocks. Match them correctly.

Extract ALL organ entries.

Return JSON:
{
  "entries": [
    {"organ_name": "Бронхи", "organ_name_lat": "Bronchi", "disease_category": "Заболевания бронхолегочной системы", "source_page": 264},
    ...
  ]
}

Rules:
- Fix obvious OCR errors in Latin names
- Keep disease category names in Russian, preserve original case
- Include source_page number from the "--- Page N ---" markers
- Include ALL entries, even if you're not 100% sure about the pairing
- Skip entries that are clearly section headers or footnotes, not organ preparations"""

        result = self.llm_call(system_prompt, full_text, max_tokens=8192)

        try:
            data = json.loads(result)
            return data.get("entries", [])
        except json.JSONDecodeError as e:
            print(f"  LLM returned invalid JSON: {e}")
            return []
