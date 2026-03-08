"""
Extractor for Tables 9-16: nosode → homeopathic remedy → effectiveness %.
Pages 403, 406, 408, 410, 412, 414, 416, 419.
"""
import re
import sqlite3
from .base import BaseExtractor, normalize_remedy_name


# Page → (table_number, disease_system)
TABLE_PAGES: dict[int, tuple[int, str]] = {
    403: (9, "Нервная система"),
    406: (10, "Сердечно-сосудистая система"),
    408: (11, "Дыхательная система и ЛОР"),
    410: (12, "Пищеварительная система и печень"),
    412: (13, "Опорно-двигательная система"),
    414: (14, "Эндокринная и иммунная системы"),
    416: (15, "Мочеполовая система"),
    419: (16, "Кожа"),
}

# Category header patterns → normalized category name
CATEGORY_PATTERNS: list[tuple[str, str]] = [
    (r"^К\s*о\s*к\s*к\s*и", "Кокки"),
    (r"^Кокки", "Кокки"),
    (r"^<окки", "Кокки"),  # OCR artifact
    (r"^Б\s*а\s*к\s*т\s*е\s*р\s*и\s*и", "Бактерии (палочки)"),
    (r"^Бактерии", "Бактерии (палочки)"),
    (r"^В\s*и\s*р\s*у\s*с\s*ы", "Вирусы"),
    (r"^Вирусы", "Вирусы"),
    (r"^В\s*И\s*Р\s*У\s*С\s*Ы", "Вирусы"),
    (r"^П\s*а\s*р\s*а\s*з\s*и\s*т\s*а\s*р\s*н", "Паразитарные"),
    (r"^Паразитарн", "Паразитарные"),
    (r"^Па\s*разитарн", "Паразитарные"),
]

# Lines to skip (noise from OCR)
SKIP_PATTERNS = [
    r"^Таблица\s+\d+",
    r"^Часто\s+вы",
    r"^этиологические\s+ф",
    r"^Соответствую",
    r"^гом\s*еопатические",
    r"^Эф\s*ф\s*ективность",
    r"^B\s*%",
    r"^B%",
    r"^Э\s*тиол\s*огически",
    r"^Соответствующие",
    r"^Эффективность",
    r"^\*",  # footnotes
    r"^Ретроспективный",
    r"^Необходимо\s+также",
    r"^После\s+",
    r"^В\s+группу",
    r"^Проводилось",
    r"^Проведенные",
    r"^Специальное",
    r"^В\s+зависимости",
    r"^На\s+2-3",
    r"^Энергоинформационные",
    r"^Учитывая",
    r"^тестирован",
    r"^конституц",
    r"^препараты",
    r"^наиболее",
    r"^парата",
    r"^нозода",
    r"^характеристик",
    r"^волновые",
    r"^Волновые",
    r"^ществ",
    r"^продуктов",
    r"^формационный",
    r"^которые",
    r"^ЭП\s",
    r"^до\s+нормы",
    r"^тронным",
    r"^После\s+определения",
    r"^теристик",
    r"^соприкасаются",
    r"^ровительные",
    r"^бранного",
    r"^и\s+эффективность",
    r"^при\s+заболевани",
    r"^при\s+патологии",
    r"^\d+\.\d+\.\d+\.",  # section numbers like "5.4.3."
    r"^Алгоритм",
    r"^Этиологические\s+факторы",
    r"^Не\s+для\s+всех",
    r"^\*\*",
    r"^Для\s+нозодов",
    r"^Вирус\s+папиллом",
    r"^Вероятно",
    r"^Этот\s+препарат",
    r"^В\s+таблицу",
    r"^Не\s+совместим",
    r"^и\s+ЛОР",
    r"^из\s+группы",
    r"^и\s+определения",
    r"^и\s+для\s+каждого",
    r"^использовани",
    r"^Сочетанное",
    r"^После\s+отбора",
    r"^приступаем",
    r"^и\s+оценка",
    r"^и\s+включение",
    r"^позволили",
    r"^определить\s+круг",
    r"^этиологическим",
    r"^наиболее\s+часто",
    r"^Staphylococcinum\s+koagulasopos",  # text mentions, not table
    r"^Streptococcinum\s+haemolyticus\s+-",  # ditto
    r"^Pneumococcinum\s+M\s*-$",  # ditto
    r"^Cytomegalovirus\s+-",  # ditto
    r"^AID",  # text mention
    r"^Human papillomavirus\s+-",  # ditto
    r"^Hepatitis\s+В",  # text mention
    r"^при\s+",  # prose start
    r"^В\s+лечебных",  # prose
    r"^Энергоинформационные\s+характер",
    r"^готовленных",
    r"^Arthritis",  # text mentions
    r"^Polyarthritis",
    r"^Rheuma",
    r"^Epicondylitis",
    r"^целях",
    r"^ожидаемого",
    r"^Не\s+совместим",
    r"^временно\s+не",
    r"^Dermatitis",
    r"^Acne",
    r"^Eczema",
    r"^Psoriasis",
    r"^Vitiligo",
    r"^Lipoma",
    r"^Melanoma",
    r"^Sclerodermia",
    r"^совместно\.$",
    r"^и\s+определения\s+исходных",
    r"^нозодов\.\s+",
    r"^нозодов\s+проводится",
    r"^Из\s+группы",
    r"^совпадени",
]

# OCR fixes specific to nosode/remedy names in tables 9-16
NOSODE_OCR_FIXES: dict[str, str] = {
    "Meninqococcinum": "Meningococcinum",
    "Adenoqrippe": "Adenogrippe",
    "Cytomeqalovirus": "Cytomegalovirus",
    "Cvtomeqalovirus": "Cytomegalovirus",
    "Cvlomeqalovirus": "Cytomegalovirus",
    "Dyphtherinum": "Diphtherinum",
    "Dyphtheriae": "Diphtheriae",
    "Peptostreptococcin u m": "Peptostreptococcinum",
    "Staphvlococcinum": "Staphylococcinum",
    "Staphylococcinum koaq.": "Staphylococcinum koag.",
    "Staphylococcinum aur., koaq.": "Staphylococcinum aur., koag.",
    "Staphylococcinum aur.koag.posit.": "Staphylococcinum aur. koag.",
    "Staphylococcinum koagulasopos.": "Staphylococcinum koag.",
    "Hyoscvamus": "Hyoscyamus",
    "Hvoscyamus": "Hyoscyamus",
    "Crataequs": "Crataegus",
    "Solidaqo": "Solidago",
    "Phytolacca +  Solidaqo": "Phytolacca + Solidago",
    "Clematis + Colocynthis": "Clematis + Colocynthis",
    "Mercurius cvanatus": "Mercurius cyanatus",
    "Mercurius cyan.+Naja": "Mercurius cyanatus + Naja",
    "Mercurius cyanatus +Naia": "Mercurius cyanatus + Naja",
    "Mercurius cvanatus +Naia": "Mercurius cyanatus + Naja",
    "Arqentum nitricum": "Argentum nitricum",
    "Antim onium  tartaricum": "Antimonium tartaricum",
    "Lemna minor +  Sambucus": "Lemna minor + Sambucus",
    "Hepar sulfur +  Silicea": "Hepar sulfur + Silicea",
    "Vincetoxicum +  Euphrasia": "Vincetoxicum + Euphrasia",
    "Phytolacca + Urtica": "Phytolacca + Urtica",
    "Phytolacca +  Urtica": "Phytolacca + Urtica",
    "Urtica + Phytolacca": "Urtica + Phytolacca",
    "Epstein -  Barr (Mononucleosis)": "Epstein-Barr",
    "Epstein -  Barr": "Epstein-Barr",
    "Epstein-Barr (Mononucleosis)": "Epstein-Barr",
    "V. Epstein-Barr": "Epstein-Barr",
    "Herpes simpl.": "Herpes simplex",
    "Herpes Zoster": "Herpes zoster",
    "iPpisthorchosis": "Opisthorchosis",
    "Crataequs + Urtica": "Crataegus + Urtica",
    "Crataequs+Urtica urens": "Crataegus + Urtica urens",
    "Convallaria + Solidaqo": "Convallaria + Solidago",
    "Grippe*": "Grippe",
    "Echinococcinum**": "Echinococcinum",
    "Echinococcinum*": "Echinococcinum",
    "Tuberculinum*": "Tuberculinum",
    "Human papillomavirus*": "Human papillomavirus",
    "Papillomavirus humani*": "Papillomavirus humani",
    "Gartner (Salmonella)": "Gartner",
    "Gartner (Salmonella)__": "Gartner",
    "PC-virus": "PC-virus",
    "V. darmkatar": "V. darmkatarrh",
    "Lamblia intestin.": "Lamblia intestinalis",
    "Mycoplasma pneum.": "Mycoplasma pneumoniae",
    "Chlamydia pneum.": "Chlamydia pneumoniae",
    "Chlamydia trachom.": "Chlamydia trachomatis",
    "Luesinum (Treponema pal.)": "Luesinum",
    "Treponema pal.": "Treponema pallidum",
    "Mycoplasma horn.": "Mycoplasma hominis",
    "Ureaplasma ur.": "Ureaplasma urealyticum",
    "Trichomonaden fl.": "Trichomonaden",
    "Staphylococcinum aur.": "Staphylococcinum aureus",
    "Pneumococcinum М": "Pneumococcinum M",
    "Pneumococcinum M": "Pneumococcinum M",
    "Solidaqo + Hamamelis": "Solidago + Hamamelis",
    "Hamamelis + Strophanthus": "Hamamelis + Strophanthus",
    "Silicea + Sulfur iodatum": "Silicea + Sulfur iodatum",
    "Secale cornutum + Galphimia": "Secale cornutum + Galphimia",
    "Scrophularia + Colchicum": "Scrophularia + Colchicum",
    "Thuia + Acidum sulfuricum": "Thuja + Acidum sulfuricum",
    "Thuia": "Thuja",
    "Drosera + Rumex": "Drosera + Rumex",
    "Clematis + Colocynthis": "Clematis + Colocynthis",
    "Antimonium crud. или arsen.": "Antimonium crudum",
    "Trichophyton rubr., mentaq.": "Trichophyton",
    "Pseudomonas aeruqinosa": "Pseudomonas aeruginosa",
    "Staphvlococcinum aur.": "Staphylococcinum aureus",
    "Staphvlococcinum aur": "Staphylococcinum aureus",
    "Hyoscvamus + Adonis vern.": "Hyoscyamus + Adonis vernalis",
    "Hyoscvamus + Adonis vern": "Hyoscyamus + Adonis vernalis",
    "Hvoscyamus": "Hyoscyamus",
    "Meninqococcinum Hvoscyamus": "SKIP",  # merged line — will be filtered
    "Cvlomeqalovirus Rhus toxicodendron": "SKIP",
    "Cvtomeqalovirus Rhus toxicodendron": "SKIP",
    "Dyphtherinum Mercurius cyan.+Naja": "SKIP",
    "Enterococcinum Hydrastis": "SKIP",
    "Carduus marianus или Carduus benedictus": "Carduus marianus",
    "Urtica urens или Urtica dioica": "Urtica urens",
    "Strophanthus + Hamamelis": "Strophanthus + Hamamelis",
    "Strophanthus +\nHamamelis": "Strophanthus + Hamamelis",
}


def _apply_ocr_fixes(text: str) -> str:
    """Apply OCR fixes to nosode/remedy names."""
    text = text.strip()
    if text in NOSODE_OCR_FIXES:
        return NOSODE_OCR_FIXES[text]
    return normalize_remedy_name(text)


def _is_percentage(text: str) -> bool:
    """Check if text is a percentage value (number between 50-100)."""
    text = text.strip()
    # Remove trailing % if present
    text = text.rstrip("%").strip()
    try:
        val = int(text)
        return 50 <= val <= 100
    except ValueError:
        return False


def _detect_category(line: str) -> str | None:
    """Detect if line is a category header. Returns normalized category or None."""
    stripped = line.strip()
    for pattern, category in CATEGORY_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return category
    return None


def _is_ocr_garbage(line: str) -> bool:
    """Detect OCR garbage lines (symbols, non-Latin/Cyrillic noise)."""
    stripped = line.strip()
    # Remove common punctuation
    clean = re.sub(r"[\s.,;:\-+*'\"()!?/\\^_#%&]", "", stripped)
    if not clean:
        return True
    # Pure numbers are NOT garbage (they can be percentages)
    if clean.isdigit():
        return False
    # Too short and non-alphabetic
    if len(clean) < 3:
        return True
    # Mostly non-letter characters (and not digits)
    letters = sum(1 for c in clean if c.isalpha())
    if letters < len(clean) * 0.4:
        return True
    return False


def _should_skip(line: str) -> bool:
    """Check if line should be skipped (noise, footnotes, prose text)."""
    stripped = line.strip()
    if not stripped:
        return True
    if len(stripped) > 120:  # Prose text, not table data
        return True
    if _is_ocr_garbage(stripped):
        return True
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True
    return False


class NosodeRemediesExtractor(BaseExtractor):
    """Extract nosode→remedy→effectiveness data from Tables 9-16."""

    # Override: keep standalone numbers 50-100 (they are effectiveness percentages)
    HEADER_PATTERNS = [
        r"^Г\.?\s*А\.?\s*Юсупов\s*$",
        r"^Энергоинформационная\s+медицина\s*$",
        r"^Раздел\s*[IІ!1]{1,2}\.?\s*ПРАКТИКА\s*$",
        r"^Раздел\s*!!\.?\s*ПРАКТИКА\s*$",
    ]

    def strip_headers(self, text: str) -> str:
        """Override: keep standalone numbers (percentages), only strip real page numbers."""
        if not text:
            return ""
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if any(re.match(p, stripped, re.IGNORECASE) for p in self.HEADER_PATTERNS):
                continue
            # Skip page numbers (3-digit, typically 400-420 range)
            if re.match(r"^\d{3}\s*$", stripped):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def extract(self) -> dict:
        print("\n=== Extracting Nosode-Remedy relationships (Tables 9-16) ===")

        all_records: list[dict] = []

        for page_num, (table_num, disease_system) in TABLE_PAGES.items():
            pages = self.fetch_pages(page_num, page_num)
            if not pages:
                print(f"  WARNING: Page {page_num} not found")
                continue

            text = self.strip_headers(pages[0]["plain_text"] or "")
            records = self._parse_table(text, page_num, table_num, disease_system)
            all_records.extend(records)
            print(f"  Table {table_num} (p.{page_num}, {disease_system}): {len(records)} records")

        # Save debug
        self.save_debug("nosode_remedies_raw", all_records)

        # Resolve IDs and insert
        conn = self.get_db_connection()
        self._resolve_and_insert(conn, all_records)

        self.preview(conn, "nosode_remedies", limit=5)
        conn.close()

        print(f"\n  TOTAL nosode_remedies: {len(all_records)} records")
        return {"records": len(all_records)}

    def _parse_table(
        self, text: str, page_num: int, table_num: int, disease_system: str
    ) -> list[dict]:
        """Parse a single table page into records using line-by-line state machine."""
        lines = text.split("\n")
        records: list[dict] = []
        current_category = None

        # State machine: collect triplets (nosode, remedy, percentage)
        buffer: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Skip noise
            if _should_skip(stripped):
                continue

            # Check for category header
            cat = _detect_category(stripped)
            if cat is not None:
                # Flush buffer before switching category
                self._flush_buffer(buffer, current_category, disease_system, page_num, table_num, records)
                buffer = []
                current_category = cat
                continue

            # Skip if no category yet
            if current_category is None:
                continue

            # Check if it's a percentage
            if _is_percentage(stripped):
                buffer.append(stripped)
                # We have a complete triplet when buffer has 3 items
                if len(buffer) >= 3:
                    self._flush_buffer(buffer, current_category, disease_system, page_num, table_num, records)
                    buffer = []
                continue

            # It's a data line (nosode name or remedy name)
            buffer.append(stripped)

            # Safety: if buffer grows too large, something is wrong
            if len(buffer) > 5:
                # Try to salvage: maybe we missed a percentage
                self._flush_buffer(buffer[:3], current_category, disease_system, page_num, table_num, records)
                buffer = buffer[3:]

        # Flush remaining
        self._flush_buffer(buffer, current_category, disease_system, page_num, table_num, records)

        return records

    def _flush_buffer(
        self,
        buffer: list[str],
        category: str | None,
        disease_system: str,
        page_num: int,
        table_num: int,
        records: list[dict],
    ) -> None:
        """Try to extract a record from the buffer."""
        if len(buffer) < 3:
            return

        # Handle multi-line remedy names: if buffer has 4+ items and last is percentage,
        # merge middle items as remedy name
        if _is_percentage(buffer[-1]):
            nosode_raw = buffer[0]
            pct_raw = buffer[-1]
            remedy_parts = buffer[1:-1]
            remedy_raw = " ".join(remedy_parts)
        else:
            return

        nosode = _apply_ocr_fixes(nosode_raw)
        remedy = _apply_ocr_fixes(remedy_raw)

        # Skip merged lines (OCR artifact)
        if nosode == "SKIP" or remedy == "SKIP":
            return

        try:
            effectiveness = int(pct_raw.strip().rstrip("%"))
        except ValueError:
            return

        # Remove OCR garbage characters
        nosode = re.sub(r'[^\w\s.,()\-+/\'"]', '', nosode).strip()
        remedy = re.sub(r'[^\w\s.,()\-+/\'"]', '', remedy).strip()

        if not nosode or not remedy:
            return

        records.append({
            "nosode_name": nosode,
            "remedy_name": remedy,
            "effectiveness": effectiveness,
            "disease_system": disease_system,
            "nosode_category": category,
            "source_page": page_num,
            "table_number": table_num,
        })

    # Manual nosode name mapping: table name → DB name (for forms that differ)
    NOSODE_ALIASES: dict[str, str] = {
        "toxoplasma": "toxoplasmose",
        "trichinella": "trichinose",
        "v. darmkatarrh": "v-darmkatarrh",
        "darmkatarrh": "v-darmkatarrh",
        "klebsiela pneumoniae": "klebsiella pneumoniae",
        "klebsiella pneumoniae": "klebsiella pneumoniae",
        "peptostreptococcinum": "peptostreptococc anaerobius",
        "faecalis ale": "alcaligenes faecalis",
        "listeria": "listeriose (listeria monocytogenes)",
        "cytomegalovirus": "cytomegalovirus",  # not in nosodes table, keep name
        "b. coli": "b.coli communis",
        "в. coli": "b.coli communis",
        "campylobacter iejuni": "campylobacter jejunii",
        "candida albicans": "candida albicans",
        "amoeben": "entamoeba histolytica (amoeben)",
        "ascariden": "ascaris lumbricoides (ascariden)",
        "encephalitis": "encephalitis",
        "staphylococcinum": "staphylococcinum aureus",
        "streptococcinum": "streptococcinum haemolyticus",
    }

    def _resolve_and_insert(self, conn: sqlite3.Connection, records: list[dict]) -> None:
        """Resolve nosode_id and remedy_id, then insert into DB."""
        # Build lookup maps
        nosode_map: dict[str, int] = {}
        for row in conn.execute("SELECT id, name_lat FROM nosodes"):
            nosode_map[row[1].lower()] = row[0]

        remedy_map: dict[str, int] = {}
        for row in conn.execute("SELECT id, name_lat FROM remedies"):
            remedy_map[row[1].lower()] = row[0]

        resolved_nosodes = 0
        resolved_remedies = 0

        for rec in records:
            # Resolve nosode_id
            nosode_lower = rec["nosode_name"].lower()
            nosode_id = nosode_map.get(nosode_lower)
            if not nosode_id:
                # Try alias mapping
                alias = self.NOSODE_ALIASES.get(nosode_lower)
                if alias:
                    nosode_id = nosode_map.get(alias)
            if not nosode_id:
                # Try partial match: find DB entry containing the first word
                first_word = nosode_lower.split()[0] if nosode_lower else ""
                if len(first_word) >= 4:
                    for name, nid in nosode_map.items():
                        if first_word in name or name.startswith(first_word):
                            nosode_id = nid
                            break
            if nosode_id:
                resolved_nosodes += 1

            # Resolve remedy_id via direct match in remedies table
            remedy_name = rec["remedy_name"]
            remedy_id = remedy_map.get(remedy_name.lower())
            if not remedy_id:
                # For combined remedies like "A + B", try resolving first component
                first_remedy = remedy_name.split("+")[0].strip().lower()
                remedy_id = remedy_map.get(first_remedy)
            if remedy_id:
                resolved_remedies += 1

            conn.execute(
                "INSERT INTO nosode_remedies "
                "(nosode_name, nosode_id, remedy_name, remedy_id, effectiveness, "
                "disease_system, nosode_category, source_page, table_number) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec["nosode_name"],
                    nosode_id,
                    rec["remedy_name"],
                    remedy_id,
                    rec["effectiveness"],
                    rec["disease_system"],
                    rec["nosode_category"],
                    rec["source_page"],
                    rec["table_number"],
                ),
            )

        conn.commit()
        print(f"  Resolved: {resolved_nosodes}/{len(records)} nosodes, "
              f"{resolved_remedies}/{len(records)} remedies")
