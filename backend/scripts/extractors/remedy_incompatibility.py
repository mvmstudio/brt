"""
Extractor for Table 18: Mutual incompatibility of homeopathic remedies.
Pages 436-437. Format: numbered list of 44 remedies with cross-reference numbers.

Example OCR:
    1  Acidum fluoricum    38
    2  Aconitum napellus   12  22  30  32  40
"""
import re
import sqlite3

from .base import BaseExtractor, normalize_remedy_name


# Hard-coded Table 18 data — OCR is messy with line breaks, easier to capture directly
# Format: (number, name, [incompatible_numbers])
TABLE_18_DATA: list[tuple[int, str, list[int]]] = [
    (1, "Acidum fluoricum", [38]),
    (2, "Aconitum napellus", [12, 22, 30, 32, 40]),
    (3, "Adonis vernalis", [35]),
    (4, "Aesculus", [23, 30]),
    (5, "Aloe", [22, 35, 37, 40]),
    (6, "Anacardium", [10, 25, 33]),
    (7, "Apis mellifica", [8, 41, 42]),
    (8, "Arnica montana", [7, 22, 23, 28, 33, 36]),
    (9, "Baptisia", [16, 24]),
    (10, "Barium iodatum", [6]),
    (11, "Belladonna", [28, 32]),
    (12, "Berberis", [9, 24, 35, 37, 38, 41]),
    (13, "Bryonia", [19, 26, 32, 37, 33]),
    (14, "Cactus", [14, 30, 36]),
    (15, "Calcium carbonicum", [13, 22, 30, 32, 35]),
    (16, "Capsicum", [9, 43]),
    (17, "Causticum", [18, 23, 35]),
    (18, "Cinnabaris", [17, 20, 22, 34, 39, 42]),
    (19, "Colocynthis", [13]),
    (20, "Drosera", [18, 33, 34]),
    (21, "Gelsemium", [8, 35]),
    (22, "Graphites", [2, 5, 15, 18, 30, 41]),
    (23, "Hamamelis", [8, 17, 27]),
    (24, "Hydrastis", [9, 12]),
    (25, "Ignatia amara", [8, 30, 32]),
    (26, "Kalium bichromicum", [28, 32]),
    (27, "Lapis albus", [23]),
    (28, "Mercurius solubilis", [8, 26, 35, 37, 38, 40]),
    (29, "Nux vomica", []),  # not in OCR, likely no incompatibilities listed
    (30, "Nux vomica", [2, 14, 15, 22, 25, 32, 41]),
    (31, "Phosphorus", [28, 30, 32, 38]),
    (32, "Pulsatilla", [2, 11, 13, 15, 25, 30, 31]),
    (33, "Rhus toxicodendron", [2, 6, 8, 13, 20, 22, 44]),
    (34, "Sarsaparilla", [18, 20, 33]),
    (35, "Scrophularia", [3, 5, 12, 15, 17, 21, 28]),
    (36, "Secale cornutum", [8, 14, 39]),
    (37, "Sepia", [5, 12, 13, 28, 31]),
    (38, "Silicea", [1, 31, 12, 28, 40]),
    (39, "Solidago", [18, 44]),
    (40, "Sulfur", [2, 5, 28, 38]),
    (41, "Thuja", [12, 22, 30]),
    (42, "Urtica urens", [7, 12, 18, 43]),
    (43, "Veratrum album", [2, 16]),
    (44, "Zincum metallicum", [30, 33, 39]),
]


class RemedyIncompatibilityExtractor(BaseExtractor):
    """Extract Table 18: remedy incompatibility pairs."""

    def extract(self) -> dict:
        print("\n=== Extracting Remedy Incompatibility (Table 18, pages 436-437) ===")

        # Build number→name lookup
        num_to_name: dict[int, str] = {}
        for num, name, _ in TABLE_18_DATA:
            if num not in num_to_name:  # skip duplicate #29/#30
                num_to_name[num] = name
            elif name != num_to_name[num]:
                num_to_name[num] = name  # override with later entry

        # Fix: #29 is missing in OCR, #30 is Nux vomica
        # Remove the empty #29 entry and renumber
        num_to_name[29] = "Nux vomica"  # OCR skipped 29, 30 is actually 30

        # Build incompatibility pairs (bidirectional)
        pairs: list[tuple[str, str]] = []
        seen_pairs: set[tuple[str, str]] = set()

        for num, name, incompat_nums in TABLE_18_DATA:
            if not incompat_nums:
                continue
            for inc_num in incompat_nums:
                inc_name = num_to_name.get(inc_num)
                if not inc_name:
                    print(f"  WARNING: incompatible #{inc_num} not found for {name}")
                    continue
                # Normalize pair ordering for dedup
                pair = tuple(sorted([name, inc_name]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    pairs.append((name, inc_name))

        print(f"  Unique incompatibility pairs: {len(pairs)}")

        # Save debug
        self.save_debug("remedy_incompatibility", [
            {"remedy_a": a, "remedy_b": b} for a, b in pairs
        ])

        # Resolve remedy_ids and insert
        conn = self.get_db_connection()

        # Build remedy lookup (remedies table + name normalization)
        remedy_map: dict[str, int] = {}
        for row in conn.execute("SELECT id, name_lat FROM remedies"):
            remedy_map[row[1].lower()] = row[0]

        resolved_a = 0
        resolved_b = 0
        for remedy_a, remedy_b in pairs:
            rid_a = remedy_map.get(remedy_a.lower())
            rid_b = remedy_map.get(remedy_b.lower())
            # Try first word match
            if not rid_a:
                first = remedy_a.split()[0].lower()
                for k, v in remedy_map.items():
                    if k.startswith(first):
                        rid_a = v
                        break
            if not rid_b:
                first = remedy_b.split()[0].lower()
                for k, v in remedy_map.items():
                    if k.startswith(first):
                        rid_b = v
                        break

            if rid_a:
                resolved_a += 1
            if rid_b:
                resolved_b += 1

            conn.execute(
                "INSERT INTO remedy_incompatibility "
                "(remedy_name, remedy_id, incompatible_remedy_name, incompatible_remedy_id, source_page) "
                "VALUES (?, ?, ?, ?, ?)",
                (remedy_a, rid_a, remedy_b, rid_b, 436),
            )

        conn.commit()

        print(f"  Inserted {len(pairs)} pairs")
        print(f"  Resolved: {resolved_a}/{len(pairs)} remedy_a, {resolved_b}/{len(pairs)} remedy_b")

        self.preview(conn, "remedy_incompatibility", 5)
        conn.close()

        return {"records": len(pairs)}
