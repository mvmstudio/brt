"""
Materia Medica extractor (pages 140-180).
Pattern: REMEDY_NAME_LAT (REMEDY_NAME_RUS), then symptoms by organ system.
~20 remedies. Pure regex/deterministic parsing — no LLM.
"""
import json
import re

from .base import BaseExtractor, normalize_latin_upper

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

# Reverse map: Russian names -> system key (include common variants from OCR)
_SECTION_ALIASES: dict[str, str] = {}
for key, rus_name in SYSTEM_MAP.items():
    _SECTION_ALIASES[rus_name.lower()] = key

# Additional aliases for OCR variants
_SECTION_ALIASES.update({
    "психика": "psyche",
    "нозологии": "nosologies",
    "склонности": "tendencies",
    "голова": "head",
    "лицо": "face",
    "глаза": "eyes",
    "уши": "ears",
    "зубы": "teeth",
    "зубы и полость рта": "teeth",
    "дыхательная система": "respiratory",
    "органы дыхания": "respiratory",
    "респираторная система": "respiratory",
    "сердечно-сосудистая система": "cardiovascular",
    "сердце и кровообращение": "cardiovascular",
    "сердце": "cardiovascular",
    "кровообращение": "cardiovascular",
    "пищеварительная система": "digestive",
    "желудочно-кишечный тракт": "digestive",
    "желудок": "digestive",
    "жкт": "digestive",
    "пищеварение": "digestive",
    "мочеполовая система": "urogenital",
    "мочевыделительная система": "urogenital",
    "почки": "urogenital",
    "мочевая система": "urogenital",
    "женские проблемы": "female",
    "у женщин": "female",
    "женская половая сфера": "female",
    "мужские проблемы": "male",
    "у мужчин": "male",
    "мужская половая сфера": "male",
    "кожа": "skin",
    "кожные проявления": "skin",
    "опорно-двигательная система": "musculoskeletal",
    "костно-мышечная система": "musculoskeletal",
    "конечности": "musculoskeletal",
    "суставы": "musculoskeletal",
    "нервная система": "nervous",
    "железы": "glands",
    "лимфатические узлы": "glands",
    "лихорадка": "fever",
    "модальность": "modality",
    "модальности": "modality",
})

# Regex for remedy headers: ACONITUM (АКОНИТУМ)
REMEDY_HEADER_RE = re.compile(
    r'^([A-Z][A-Z ]+?)\s*\(([А-ЯЁ][А-ЯЁа-яё ]+?)\)\s*$'
)

# Regex for section headers within a remedy block
# Matches: "Психика.", "Психика:", "Голова:", "Женские проблемы.", etc.
# Must start at beginning of a logical segment (after newline or period+space)
SECTION_HEADER_RE = re.compile(
    r'(?:^|\n)\s*'
    r'(Психика|Нозологии|Склонности|Голова|Лицо|Глаза|Уши|Зубы(?:\s+и\s+полость\s+рта)?|'
    r'Дыхательная\s+система|Органы\s+дыхания|Респираторная\s+система|'
    r'Сердечно-сосудистая\s+система|Сердце(?:\s+и\s+кровообращение)?|Кровообращение|'
    r'Пищеварительная\s+система|Желудочно-кишечный\s+тракт|Желудок|ЖКТ|Пищеварение|'
    r'Мочеполовая\s+система|Мочевыделительная\s+система|Почки|Мочевая\s+система|'
    r'Женские\s+проблемы|У\s+женщин|Женская\s+половая\s+сфера|'
    r'Мужские\s+проблемы|У\s+мужчин|Мужская\s+половая\s+сфера|'
    r'Кожа|Кожные\s+проявления|'
    r'Опорно-двигательная\s+система|Костно-мышечная\s+система|Конечности|Суставы|'
    r'Нервная\s+система|'
    r'Железы|Лимфатические\s+узлы|'
    r'Лихорадка|'
    r'Модальност[ьи])'
    r'\s*[.:]\s*',
    re.IGNORECASE
)


class MateriaMedicaExtractor(BaseExtractor):
    START_PAGE = 140
    END_PAGE = 180

    def extract(self) -> dict:
        print("\n=== Materia Medica (pages 140-180) ===")

        # 1. Fetch and concat all pages with page numbers
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)
        page_texts: list[tuple[int, str]] = []
        for p in pages:
            text = self.strip_headers(p["plain_text"] or "")
            if text:
                page_texts.append((p["page_num"], text))

        full_text = "\n".join(t for _, t in page_texts)

        # 2. Trim intro text — start from first remedy header
        first_match = REMEDY_HEADER_RE.search(full_text)
        if first_match:
            full_text = full_text[first_match.start():]

        # 3. Split into remedy blocks
        blocks = self._split_into_remedy_blocks(full_text)
        print(f"  Found {len(blocks)} remedy blocks")

        # 4. Parse each block with regex (no LLM)
        all_remedies = []
        for block in blocks:
            remedy = self._parse_remedy_block(block)
            all_remedies.append(remedy)
            sys_count = len(remedy.get("symptoms", []))
            print(f"  {remedy['name_lat']}: {sys_count} sections")

        # 5. Save debug
        self.save_debug("materia_medica", all_remedies)

        # 6. Insert into DB
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
                if current_block:
                    blocks.append(current_block)
                current_block = {
                    "name_lat": match.group(1).strip(),
                    "name_rus": match.group(2).strip(),
                    "text": "",
                }
            elif current_block:
                current_block["text"] += line + "\n"

        if current_block:
            blocks.append(current_block)

        # Trim — remove therapeutic index intro if it leaked in
        for block in blocks:
            marker = "Терапевтический указатель"
            pos = block["text"].find(marker)
            if pos > 0:
                block["text"] = block["text"][:pos].strip()

        return blocks

    def _parse_remedy_block(self, block: dict) -> dict:
        """Parse a remedy block into structured data using regex for section headers."""
        name_lat_normalized = normalize_latin_upper(block["name_lat"])
        text = block["text"].strip()

        # Find all section headers with their positions
        sections: list[tuple[str, int, int]] = []  # (system_key, start_of_content, end_of_header_match)
        for match in SECTION_HEADER_RE.finditer(text):
            header_text = match.group(1).strip().lower()
            system_key = _SECTION_ALIASES.get(header_text)
            if system_key:
                sections.append((system_key, match.end(), match.start()))

        # Extract symptoms for each section
        symptoms = []
        for i, (system_key, content_start, _header_start) in enumerate(sections):
            # Content ends at the start of the next section header, or end of text
            if i + 1 < len(sections):
                content_end = sections[i + 1][2]  # start of next header match
            else:
                content_end = len(text)

            content = text[content_start:content_end].strip()
            # Clean up: collapse whitespace, remove trailing newlines
            content = re.sub(r'\s*\n\s*', ' ', content).strip()
            content = content.rstrip(".,;:-")

            if content and len(content) > 5:
                system_name = SYSTEM_MAP.get(system_key, system_key)
                symptoms.append({
                    "system": system_key,
                    "system_name": system_name,
                    "description": content,
                })

        # Build summary from first ~200 chars of text before first section, or first section
        summary = ""
        if sections:
            pre_section = text[:sections[0][2]].strip()
            pre_section = re.sub(r'\s*\n\s*', ' ', pre_section).strip()
            if len(pre_section) > 20:
                summary = pre_section[:250].rstrip(".,;:- ") + ("..." if len(pre_section) > 250 else "")
        if not summary and symptoms:
            summary = symptoms[0]["description"][:250].rstrip(".,;:- ") + "..."

        return {
            "name_lat": name_lat_normalized,
            "name_rus": block["name_rus"],
            "summary": summary,
            "symptoms": symptoms,
            "source_pages": [],
        }
