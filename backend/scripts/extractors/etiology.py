"""
Etiology extractor (pages 224-230).
Pattern: ALL-CAPS disease system header, then typed lists (Вирусы:, Бактерии (кокки):, etc.)
"""
import json
import re

from .base import BaseExtractor

# Mapping from Russian agent type labels to normalized keys
AGENT_TYPE_MAP = {
    "вирусы": "virus",
    "бактерии (кокки)": "bacteria_cocci",
    "бактерии (палочки)": "bacteria_bacilli",
    "паразиты и грибы": "parasite_fungi",
    "паразиты и грибки": "parasite_fungi",
}


class EtiologyExtractor(BaseExtractor):
    START_PAGE = 224
    END_PAGE = 230

    # Pattern for disease system headers (ALL CAPS cyrillic)
    SYSTEM_HEADER_RE = re.compile(r'^ЗАБОЛЕВАНИЯ?\s+(.+?)(?:\s+И\s+|\s*$)', re.IGNORECASE)

    # Pattern for agent type labels
    AGENT_TYPE_RE = re.compile(
        r'^(Вирусы|Бактерии\s*\(кокки\)|Бактерии\s*\(палочки\)|Паразиты\s+и\s+гриб[ыки]+)\s*[:;]\s*',
        re.IGNORECASE,
    )

    def extract(self) -> dict:
        print("\n=== Etiology (pages 224-230) ===")

        # 1. Fetch and concat all pages
        pages = self.fetch_pages(self.START_PAGE, self.END_PAGE)
        raw_texts = []
        page_map = {}  # track which page each section starts on
        char_offset = 0
        for p in pages:
            text = self.strip_headers(p["plain_text"] or "")
            if text:
                page_map[char_offset] = p["page_num"]
                raw_texts.append(text)
                char_offset += len(text) + 1  # +1 for join newline

        full_text = "\n".join(raw_texts)

        # 2. Trim intro text — start from first disease system header
        first_system = re.search(r'^ЗАБОЛЕВАНИ', full_text, re.MULTILINE)
        if first_system:
            full_text = full_text[first_system.start():]

        # 3. Parse sections
        entries = self._parse_sections(full_text)
        print(f"  Parsed {len(entries)} entries via regex")

        # 4. Save debug
        self.save_debug("etiology", entries)

        # 5. Insert into DB
        conn = self.get_db_connection()
        try:
            for entry in entries:
                conn.execute(
                    "INSERT INTO etiology (disease_system, agent_type, agent_name, agent_name_rus, source_page) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (entry["disease_system"], entry["agent_type"], entry["agent_name"],
                     entry.get("agent_name_rus"), entry.get("source_page")),
                )
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM etiology").fetchone()[0]
            print(f"  Inserted {count} records into etiology")

            # Stats by disease system
            cursor = conn.execute(
                "SELECT disease_system, COUNT(*) FROM etiology GROUP BY disease_system ORDER BY COUNT(*) DESC LIMIT 5"
            )
            print("  Top 5 systems:")
            for row in cursor:
                print(f"    {row[0]}: {row[1]} agents")

            self.preview(conn, "etiology")
            return {"records": count}
        finally:
            conn.close()

    def _parse_sections(self, text: str) -> list[dict]:
        """Parse disease system sections with agent type sublists."""
        entries = []
        current_system = None
        current_agent_type = None
        current_agents_text = ""

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            # Check for disease system header (ALL CAPS line with "ЗАБОЛЕВАНИЯ")
            if self._is_system_header(stripped):
                # Flush previous agent list
                if current_system and current_agent_type and current_agents_text:
                    entries.extend(self._parse_agents(current_system, current_agent_type, current_agents_text))
                    current_agents_text = ""
                    current_agent_type = None

                current_system = self._clean_system_name(stripped)
                continue

            # Check for agent type label
            agent_match = self.AGENT_TYPE_RE.match(stripped)
            if agent_match:
                # Flush previous agent list
                if current_system and current_agent_type and current_agents_text:
                    entries.extend(self._parse_agents(current_system, current_agent_type, current_agents_text))

                type_label = agent_match.group(1).strip().lower()
                current_agent_type = AGENT_TYPE_MAP.get(type_label, type_label)
                # Rest of the line after the label is agent names
                current_agents_text = stripped[agent_match.end():]
                continue

            # Continuation line — append to current agents
            if current_system and current_agent_type:
                current_agents_text += " " + stripped

        # Flush last section
        if current_system and current_agent_type and current_agents_text:
            entries.extend(self._parse_agents(current_system, current_agent_type, current_agents_text))

        return entries

    def _is_system_header(self, line: str) -> bool:
        """Check if line is a disease system header (mostly ALL CAPS cyrillic)."""
        # Must contain "ЗАБОЛЕВАН"
        if "ЗАБОЛЕВАН" not in line.upper():
            return False
        # Check that the line is mostly uppercase
        cyrillic_upper = len(re.findall(r'[А-ЯЁ]', line))
        cyrillic_lower = len(re.findall(r'[а-яё]', line))
        total = cyrillic_upper + cyrillic_lower
        if total == 0:
            return False
        return cyrillic_upper / total > 0.6

    def _clean_system_name(self, line: str) -> str:
        """Normalize system name: title case, trim."""
        # Remove ГЛАВА prefix if present
        line = re.sub(r'^ГЛАВА\s+\d+\.\s*', '', line)
        # Convert from ALL CAPS to title case
        words = line.strip().split()
        result = []
        for w in words:
            if w.upper() == w and len(w) > 1:
                result.append(w.capitalize())
            else:
                result.append(w)
        return " ".join(result)

    def _parse_agents(self, system: str, agent_type: str, text: str) -> list[dict]:
        """Parse comma-separated agent names from text."""
        text = text.strip().rstrip(".")
        parts = [p.strip() for p in text.split(",")]
        entries = []
        for part in parts:
            cleaned = part.strip().strip(".,;:")
            if len(cleaned) < 2:
                continue
            if re.match(r'^\d+$', cleaned):
                continue
            entries.append({
                "disease_system": system,
                "agent_type": agent_type,
                "agent_name": cleaned,
            })
        return entries
