"""
Extractor for Table 17: Disease → etiology nosode combinations → patient count → %.
Pages 434-435.

Format:
    Заболевание  | n пациентов | Комбинации нозодов | %
    Головные боли  137  Meningococcinum + Proteus  74
                       Staphylococcinum spp, ... (в различных комбинациях)  26

Each disease has 2 rows: primary combination (high %) and secondary (lower %).
"""
import re
import sqlite3

from .base import BaseExtractor


# Hard-coded Table 17 data from OCR (pages 434-435)
# Format: (condition_name, patient_count, [(nosode_combination, percentage)])
TABLE_17_DATA: list[tuple[str, int, list[tuple[str, int]]]] = [
    ("Головные боли", 137, [
        ("Meningococcinum + Proteus", 74),
        ("Staphylococcinum spp, Pneumococcinum, P. aeroginosa, Toxoplasma, Herpes s.", 26),
    ]),
    ("Эпилепсия", 29, [
        ("Encephalitis + Tetanus", 63),
        ("Encephalitis japan, Toxoplasma, Herpes s., Echinococcinum, Cytomegalovirus, Mononucleosis, Meningococcinum, Trichinella", 37),
    ]),
    ("ИБС и гипертония", 244, [
        ("Staphylococcinum spp + Herpes s.", 79),
        ("Streptococcinum spp, Cytomegalovirus, Mononucleosis, Diphtherinum, Toxoplasma, Tetanus, Listeria", 21),
    ]),
    ("Артриты, артрозы", 327, [
        ("Streptococcinum + Proteus + Trichinella + Herpes s. или Cytomegalovirus", 82),
        ("Staphylococcinum spp, Pneumococcinum, Diphtherinum, Tetanus, B.coli, Salmonella, Yersinia, Klebsiella pn., Borrelia, Chlamydia trach., Mycobact. tub., Brucella, Toxoplasma", 18),
    ]),
    ("Сахарный диабет", 47, [
        ("Staphylococcinum spp + Cytomegalovirus + Mononucleosis", 74),
        ("Streptococcinum spp, Herpes s., Toxoplasma, Tetanus", 26),
    ]),
    ("Гипотиреоз, зоб", 86, [
        ("Streptococcinum + Cytomegalovirus + Mononucleosis", 78),
        ("Staphylococcinum spp, Herpes s., Toxoplasma, Tetanus, Chlamydia pneum.", 22),
    ]),
    ("Язвенная болезнь", 93, [
        ("Helicobacter pylori + Herpes s.", 84),
        ("Streptococcinum spp, Salmonella, B.coli, Yersinia, Candida, Lamblia", 16),
    ]),
    ("Хронический гастрит", 188, [
        ("Helicobacter pylori + Proteus + Herpes s.", 67),
        ("Streptococcinum, Staphylococcinum, Salmonella, B.coli, Yersinia, Candida, Lamblia, Cytomegalovirus", 33),
    ]),
    ("Неспецифический язвенный колит", 26, [
        ("Dysentery + Proteus + Cytomegalovirus или Mononucleosis", 72),
        ("Streptococcinum, Staphylococcinum, Salmonella, B.coli, Yersinia, Candida, Lamblia", 28),
    ]),
    ("Хронический холецистит", 142, [
        ("Proteus + Salmonella + Lamblia + Herpes s.", 74),
        ("Streptococcinum, Staphylococcinum, B.coli, Yersinia, Candida, Cytomegalovirus, Mononucleosis", 26),
    ]),
    ("Хронический пиелонефрит", 119, [
        ("B.coli + Proteus + Herpes s.", 78),
        ("Staphylococcinum, Streptococcinum, Klebsiella pn., Pseudomonas aer., Candida, Cytomegalovirus", 22),
    ]),
    ("Мочекаменная болезнь", 46, [
        ("B.coli + Proteus + Herpes progenitalis + Chlamydia trach.", 83),
        ("Staphylococcinum, Klebsiella, Pseudomonas, Candida", 17),
    ]),
    ("Аденома простаты", 118, [
        ("Herpes progenitalis + Chlamydia trachomatis", 89),
        ("Cytomegalovirus, Mononucleosis, Gonococcinum, Trichomonada, Ureaplasma, Mycoplasma", 11),
    ]),
    ("Миома матки", 437, [
        ("Herpes progenitalis + Chlamydia trachomatis", 100),
        ("Cytomegalovirus, Mononucleosis, Gonococcinum, Enterococcinum, B.coli, Mycobact. tub., Gardnerella, Trichomonada, Ureaplasma, Mycoplasma, Brucella, Toxoplasma", 0),
    ]),
    ("Бронхиальная астма", 214, [
        ("Streptococcinum + Adenoviren + Ascariden + Trichophyton", 69),
        ("Staphylococcinum spp, Meningococcinum, Pneumococcinum, Haemophilus, Mycoplasma pn., Chlamydia pn., Oxyuris, Candida, Cytomegalovirus, Mononucleosis", 31),
    ]),
    ("Хронический бронхит", 163, [
        ("Streptococcinum + Klebsiella pn. + Adenoviren", 72),
        ("Staphylococcinum, Meningococcinum, Pneumococcinum, Haemophilus, Mycoplasma pn., Chlamydia pn., Pseudomonas, Mycobact. tub., Cytomegalovirus", 28),
    ]),
    ("Отек Квинке", 18, [
        ("Staphylococcinum spp + Trichinella + Cytomegalovirus или Mononucleosis", 89),
        ("Streptococcinum, Salmonella, Amoeben, Oxyuris, Ascariden, Candida alb., Lamblia, Cytomegalovirus, Mononucleosis", 11),
    ]),
    ("Поллиноз", 97, [
        ("Streptococcinum + Proteus + Adenoviren + Trichinella", 67),
        ("Staphylococcinum spp, Meningococcinum, Klebsiella pn., Moraxella kat., Haemophilus infl., Mycoplasma pn., Chlamydia pn., Oxyuris, Ascariden, Candida alb., Cytomegalovirus, Mononucleosis", 33),
    ]),
    ("Аллергический дерматит", 74, [
        ("Streptococcinum + Dysentery + Cytomegalovirus или ЭБВ + Trichophyton", 58),
        ("Staphylococcinum, Yersinia, Salmonella, Oxyuris, Ascariden, Candida alb., Lamblia, Cytomegalovirus, ЭБВ", 42),
    ]),
]


class ConditionNosodesExtractor(BaseExtractor):
    """Extract Table 17: disease → nosode combinations with patient statistics."""

    def extract(self) -> dict:
        print("\n=== Extracting Condition-Nosodes (Table 17, pages 434-435) ===")

        conn = self.get_db_connection()

        # Build condition lookup for resolving IDs
        cond_map: dict[str, int] = {}
        for row in conn.execute("SELECT id, condition_name FROM therapeutic_index"):
            cond_map[row[1].lower()] = row[0]

        # Condition name aliases (table 17 names → therapeutic_index names)
        COND_ALIASES: dict[str, str] = {
            "исб и гипертония": "артериальная гипертония",
            "ибс и гипертония": "артериальная гипертония",
            "артриты, артрозы": "артрит (воспаление сустава)",
            "сахарный диабет": "диабет",
            "гипотиреоз, зоб": "гипотиреоз",
            "язвенная болезнь": "язва желудка и двенадцатиперстной кишки",
            "хронический гастрит": "гастрит острый",
            "хронический холецистит": "желчная колика и хронический холецистит",
            "хронический пиелонефрит": "нефрит хронический",
            "миома матки": "фибромиома матки",
            "хронический бронхит": "бронхит",
            "бронхиальная астма": "астма бронхиальная",
            "аллергический дерматит": "аллергические высыпания (крапивница)",
            "поллиноз": "аллергический насморк (поллиноз сенная лихорадка)",
            "отек квинке": "аллергические высыпания (крапивница)",
        }

        records = []
        resolved = 0

        for condition_name, patient_count, combinations in TABLE_17_DATA:
            # Resolve condition_id
            cond_lower = condition_name.lower()
            cond_id = cond_map.get(cond_lower)
            if not cond_id:
                # Try alias
                alias = COND_ALIASES.get(cond_lower)
                if alias:
                    cond_id = cond_map.get(alias)
            if not cond_id:
                # Partial match
                for k, v in cond_map.items():
                    if cond_lower.split()[0] in k or k.startswith(cond_lower.split()[0]):
                        cond_id = v
                        break
            if cond_id:
                resolved += 1

            for nosode_combination, percentage in combinations:
                rec = {
                    "condition_name": condition_name,
                    "condition_id": cond_id,
                    "nosode_names": nosode_combination,
                    "patient_count": patient_count,
                    "percentage": percentage,
                    "is_primary": percentage == max(p for _, p in combinations),
                    "source_page": 434,
                }
                records.append(rec)

        print(f"  Parsed {len(records)} records ({len(TABLE_17_DATA)} conditions)")
        print(f"  Resolved: {resolved}/{len(TABLE_17_DATA)} conditions")

        # Save debug
        self.save_debug("condition_nosodes", records)

        # Insert
        for rec in records:
            conn.execute(
                "INSERT INTO condition_nosodes "
                "(condition_name, condition_id, nosode_names, patient_count, "
                "percentage, is_primary, source_page) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rec["condition_name"],
                    rec["condition_id"],
                    rec["nosode_names"],
                    rec["patient_count"],
                    rec["percentage"],
                    1 if rec["is_primary"] else 0,
                    rec["source_page"],
                ),
            )
        conn.commit()

        print(f"  Inserted {len(records)} records into condition_nosodes")
        self.preview(conn, "condition_nosodes", 5)
        conn.close()

        return {"records": len(records)}
