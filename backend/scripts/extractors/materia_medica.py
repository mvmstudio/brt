"""
Materia Medica extractor (pages 140-180).
Pattern: REMEDY_NAME_LAT (REMEDY_NAME_RUS), then symptoms by organ system.
~20 remedies, LLM-assisted extraction of organ systems.
"""
import json
import re

from .base import BaseExtractor

# Organ system mapping (key -> Russian display name)
SYSTEM_MAP = {
    "psyche": "Психика",
    "nosologies": "Нозологии",
    "tendencies": "Склонности",
    "head": "Голова",
    "face": "Лицо",
    "eyes": "Глаза",
    "ears": "Уши",
    "teeth": "Зубы",
    "respiratory": "Дыхательная система",
    "cardiovascular": "Сердечно-сосудистая система",
    "digestive": "Пищеварительная система",
    "urogenital": "Мочеполовая система",
    "female": "У женщин",
    "male": "У мужчин",
    "skin": "Кожа",
    "musculoskeletal": "Опорно-двигательная система",
    "nervous": "Нервная система",
    "glands": "Железы",
    "fever": "Лихорадка",
    "modality": "Модальность",
}

# Regex for remedy headers: ACONITUM (АКОНИТУМ)
REMEDY_HEADER_RE = re.compile(
    r'^([A-Z][A-Z ]+?)\s*\(([А-ЯЁ][А-ЯЁа-яё ]+?)\)\s*$'
)


class MateriaMedicaExtractor(BaseExtractor):
    START_PAGE = 140
    END_PAGE = 180

    def extract(self) -> dict:
        print("\n=== Materia Medica (pages 140-180) ===")

        # 1. Fetch and concat all pages
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)
        raw_texts = []
        for p in pages:
            text = self.strip_headers(p["plain_text"] or "")
            if text:
                raw_texts.append(text)
        full_text = "\n".join(raw_texts)

        # 2. Trim intro text — start from first remedy header
        first_match = REMEDY_HEADER_RE.search(full_text, re.MULTILINE)
        if first_match:
            full_text = full_text[first_match.start():]

        # 3. Split into remedy blocks
        blocks = self._split_into_remedy_blocks(full_text)
        print(f"  Found {len(blocks)} remedy blocks")

        # 4. Process each block with LLM (batch 3-4 at a time)
        all_remedies = []
        batch_size = 3
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            batch_names = [b["name_lat"] for b in batch]
            print(f"  Processing batch: {', '.join(batch_names)}")
            results = self._extract_batch(batch)

            # Fix LLM name confusion: enforce original block names
            for j, result in enumerate(results):
                if j < len(batch):
                    expected = batch[j]["name_lat"]
                    if result.get("name_lat", "").upper() != expected.upper():
                        print(f"    Name fix: LLM returned '{result.get('name_lat')}' but expected '{expected}'")
                        result["name_lat"] = expected
                        result["name_rus"] = batch[j]["name_rus"]

            all_remedies.extend(results)

        # 5. Save debug
        self.save_debug("materia_medica", all_remedies)

        # 6. Deduplicate by name_lat (LLM may return same remedy in different batches)
        seen = {}
        deduplicated = []
        for remedy in all_remedies:
            key = remedy["name_lat"].upper().strip()
            if key not in seen:
                seen[key] = remedy
                deduplicated.append(remedy)
            else:
                # Merge symptoms from duplicate
                existing = seen[key]
                existing.setdefault("symptoms", []).extend(remedy.get("symptoms", []))
        all_remedies = deduplicated

        # 7. Insert into DB
        conn = self.get_db_connection()
        try:
            remedy_count = 0
            symptom_count = 0
            for remedy in all_remedies:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO remedies (name_lat, name_rus, source_pages, summary) "
                    "VALUES (?, ?, ?, ?)",
                    (remedy["name_lat"], remedy.get("name_rus"),
                     json.dumps(remedy.get("source_pages", []), ensure_ascii=False),
                     remedy.get("summary")),
                )
                remedy_id = cursor.lastrowid
                if remedy_id is None or remedy_id == 0:
                    # Already existed, fetch its id
                    row = conn.execute(
                        "SELECT id FROM remedies WHERE name_lat = ?", (remedy["name_lat"],)
                    ).fetchone()
                    if row:
                        remedy_id = row[0]
                    else:
                        continue
                remedy_count += 1

                for symptom in remedy.get("symptoms", []):
                    conn.execute(
                        "INSERT INTO remedy_symptoms (remedy_id, system, system_name, description) "
                        "VALUES (?, ?, ?, ?)",
                        (remedy_id, symptom["system"], symptom["system_name"], symptom["description"]),
                    )
                    symptom_count += 1

            conn.commit()
            print(f"  Inserted {remedy_count} remedies, {symptom_count} symptoms")
            self.preview(conn, "remedies")
            self.preview(conn, "remedy_symptoms")
            return {"remedies": remedy_count, "remedy_symptoms": symptom_count}
        finally:
            conn.close()

    def _split_into_remedy_blocks(self, text: str) -> list[dict]:
        """Split text into remedy blocks using regex on headers."""
        blocks = []
        lines = text.split("\n")
        current_block = None

        for line in lines:
            match = REMEDY_HEADER_RE.match(line.strip())
            if match:
                # Save previous block
                if current_block:
                    blocks.append(current_block)
                current_block = {
                    "name_lat": match.group(1).strip(),
                    "name_rus": match.group(2).strip(),
                    "text": "",
                }
            elif current_block:
                current_block["text"] += line + "\n"

        # Last block
        if current_block:
            blocks.append(current_block)

        # Trim text for each block — remove therapeutic index intro if it leaked in
        for block in blocks:
            marker = "Терапевтический указатель"
            pos = block["text"].find(marker)
            if pos > 0:
                block["text"] = block["text"][:pos].strip()

        return blocks

    def _extract_batch(self, batch: list[dict]) -> list[dict]:
        """Use LLM to extract structured symptoms from a batch of remedy blocks."""
        system_keys = list(SYSTEM_MAP.keys())
        system_prompt = f"""You are a homeopathic medicine expert extracting structured data from remedy descriptions.

For each remedy, extract symptoms organized by body system. Use ONLY these system keys:
{json.dumps(SYSTEM_MAP, ensure_ascii=False, indent=2)}

Return JSON:
{{
  "remedies": [
    {{
      "name_lat": "ACONITUM",
      "name_rus": "АКОНИТУМ",
      "summary": "1-2 sentence summary of the remedy",
      "symptoms": [
        {{"system": "psyche", "system_name": "Психика", "description": "Full symptom text for this system"}},
        ...
      ]
    }}
  ]
}}

Rules:
- Keep symptom descriptions in RUSSIAN, preserve the original text as closely as possible
- Combine multiline descriptions for the same system into one entry
- Map Russian section headers to the closest system key:
  "Психика" → psyche, "Нозологии" → nosologies, "Голова" → head, etc.
  "Желудочно-кишечный тракт" / "Пищеварительная система" → digestive
  "Сердце и кровообращение" / "Сердечно-сосудистая система" → cardiovascular
  "Женские проблемы" / "У женщин" → female
  "Мужские проблемы" / "У мужчин" → male
  "Опорно-двигательная система" / "Костно-мышечная" → musculoskeletal
  "Модальности" → modality, "Лихорадка" → fever, "Склонности" → tendencies
- If a section doesn't match any system, use the closest one
- Include ALL symptoms mentioned in the text"""

        # Build user prompt with all blocks in the batch
        remedy_names = [f"{b['name_lat']} ({b['name_rus']})" for b in batch]
        blocks_text = f"IMPORTANT: Extract exactly these {len(batch)} remedies: {', '.join(remedy_names)}\n"
        blocks_text += "Use EXACTLY these name_lat values in your response.\n"
        for block in batch:
            blocks_text += f"\n\n=== {block['name_lat']} ({block['name_rus']}) ===\n{block['text'][:6000]}"

        result = self.llm_call(system_prompt, blocks_text.strip(), max_tokens=8192)

        try:
            data = json.loads(result)
            remedies = data.get("remedies", [])
            return remedies
        except json.JSONDecodeError as e:
            print(f"  LLM returned invalid JSON: {e}")
            # Fallback: create minimal entries
            return [
                {"name_lat": b["name_lat"], "name_rus": b["name_rus"], "symptoms": []}
                for b in batch
            ]
