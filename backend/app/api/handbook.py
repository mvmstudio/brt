"""
Handbook API — structured data from the book.
Sections: therapeutic index, materia medica, nosodes, etiology, organ preparations.
"""
import json

from fastapi import APIRouter, HTTPException, Query

from app.db.connection import get_db

router = APIRouter()


# ─── Search across all handbook data ──────────────────────────────

@router.get("/handbook/search")
async def handbook_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    db = await get_db()
    rows = await db.execute_fetchall(
        """
        SELECT type, name,
               snippet(handbook_fts, 2, '<mark>', '</mark>', '...', 40) as snippet,
               entity_id, rank
        FROM handbook_fts
        WHERE handbook_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (q, limit),
    )
    results = []
    for r in rows:
        d = dict(r)
        # FTS5 returns entity_id as TEXT; cast to int for frontend matching
        if d.get("entity_id") is not None:
            try:
                d["entity_id"] = int(d["entity_id"])
            except (ValueError, TypeError):
                pass
        results.append(d)
    return {"results": results, "total": len(results)}


# ─── Therapeutic Index (conditions → remedies) ────────────────────

@router.get("/handbook/conditions")
async def list_conditions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, condition_name, remedies_list, source_page "
        "FROM therapeutic_index ORDER BY condition_name LIMIT ? OFFSET ?",
        (limit, offset),
    )
    total = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM therapeutic_index")

    results = []
    for r in rows:
        d = dict(r)
        d["remedies"] = json.loads(d.pop("remedies_list"))
        results.append(d)

    return {"results": results, "total": total[0]["cnt"]}


@router.get("/handbook/conditions/{condition_id}")
async def get_condition(condition_id: int):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, condition_name, remedies_list, source_page "
        "FROM therapeutic_index WHERE id = ?",
        (condition_id,),
    )
    if not rows:
        raise HTTPException(404, "Condition not found")

    d = dict(rows[0])
    remedy_names = json.loads(d.pop("remedies_list"))
    d["remedies"] = remedy_names

    # Enrich: resolve remedy names against remedies table (direct name match)
    enriched = []
    for name in remedy_names:
        matched = await db.execute_fetchall(
            "SELECT id, name_lat, name_rus, summary FROM remedies "
            "WHERE name_lat = ? COLLATE NOCASE",
            (name,),
        )
        if matched:
            enriched.append(dict(matched[0]))
        else:
            enriched.append({"name_lat": name, "name_rus": None, "summary": None, "id": None})

    d["remedies_details"] = enriched
    return d


# ─── Materia Medica (remedies + symptoms) ─────────────────────────

@router.get("/handbook/remedies")
async def list_remedies(
    limit: int = Query(600, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, name_lat, name_rus, summary FROM remedies "
        "ORDER BY name_lat LIMIT ? OFFSET ?",
        (limit, offset),
    )
    total = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM remedies")
    return {"results": [dict(r) for r in rows], "total": total[0]["cnt"]}


@router.get("/handbook/remedies/{remedy_id}")
async def get_remedy(remedy_id: int):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, name_lat, name_rus, source_pages, summary FROM remedies WHERE id = ?",
        (remedy_id,),
    )
    if not rows:
        raise HTTPException(404, "Remedy not found")

    d = dict(rows[0])
    if d.get("source_pages"):
        d["source_pages"] = json.loads(d["source_pages"])

    # Symptoms grouped by system
    symptom_rows = await db.execute_fetchall(
        "SELECT system, system_name, description FROM remedy_symptoms "
        "WHERE remedy_id = ? ORDER BY id",
        (remedy_id,),
    )
    d["symptoms"] = [dict(s) for s in symptom_rows]

    # Related conditions: find conditions whose remedies_list contains this remedy name
    name_lat = d["name_lat"]
    condition_rows = await db.execute_fetchall(
        "SELECT id, condition_name FROM therapeutic_index "
        "WHERE remedies_list LIKE ? COLLATE NOCASE "
        "ORDER BY condition_name",
        (f'%{name_lat}%',),
    )
    d["related_conditions"] = [
        {"id": c["id"], "condition_name": c["condition_name"]}
        for c in condition_rows
    ]

    return d


# ─── Nosodes ──────────────────────────────────────────────────────

@router.get("/handbook/nosodes")
async def list_nosodes(
    category: str | None = Query(None, description="Filter: bacteria, virus, etc."),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()

    where = ""
    params: list = []
    if category:
        where = "WHERE category = ?"
        params.append(category)

    rows = await db.execute_fetchall(
        f"SELECT id, number, name_lat, name_rus, category, source_page "
        f"FROM nosodes {where} ORDER BY number LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    total = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM nosodes {where}", params,
    )

    # Available categories for filter UI
    cats = await db.execute_fetchall(
        "SELECT DISTINCT category FROM nosodes WHERE category IS NOT NULL ORDER BY category"
    )

    return {
        "results": [dict(r) for r in rows],
        "total": total[0]["cnt"],
        "categories": [c["category"] for c in cats],
    }


# ─── Etiology ─────────────────────────────────────────────────────

@router.get("/handbook/etiology")
async def list_etiology(
    disease_system: str | None = Query(None, description="Filter by disease system"),
    agent_type: str | None = Query(None, description="Filter: virus, bacteria_cocci, etc."),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    db = await get_db()

    conditions = []
    params: list = []
    if disease_system:
        conditions.append("disease_system = ?")
        params.append(disease_system)
    if agent_type:
        conditions.append("agent_type = ?")
        params.append(agent_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.execute_fetchall(
        f"SELECT id, disease_system, agent_type, agent_name, agent_name_rus, source_page "
        f"FROM etiology {where} ORDER BY disease_system, agent_type, agent_name LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    total = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM etiology {where}", params,
    )

    # Available filters
    systems = await db.execute_fetchall(
        "SELECT DISTINCT disease_system FROM etiology ORDER BY disease_system"
    )
    types = await db.execute_fetchall(
        "SELECT DISTINCT agent_type FROM etiology ORDER BY agent_type"
    )

    return {
        "results": [dict(r) for r in rows],
        "total": total[0]["cnt"],
        "disease_systems": [s["disease_system"] for s in systems],
        "agent_types": [t["agent_type"] for t in types],
    }


# ─── Organ Preparations ──────────────────────────────────────────

@router.get("/handbook/organs")
async def list_organ_preparations(
    category: str | None = Query(None, description="Filter by disease category"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()

    where = ""
    params: list = []
    if category:
        where = "WHERE disease_category = ?"
        params.append(category)

    rows = await db.execute_fetchall(
        f"SELECT id, disease_category, organ_name, organ_name_lat, manufacturer, source_page "
        f"FROM organ_preparations {where} ORDER BY disease_category, organ_name LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    total = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM organ_preparations {where}", params,
    )

    cats = await db.execute_fetchall(
        "SELECT DISTINCT disease_category FROM organ_preparations "
        "WHERE disease_category IS NOT NULL ORDER BY disease_category"
    )

    return {
        "results": [dict(r) for r in rows],
        "total": total[0]["cnt"],
        "categories": [c["disease_category"] for c in cats],
    }


# ─── Relations (cross-entity) ────────────────────────────────────

ENTITY_TYPES = {"condition", "remedy", "nosode", "etiology", "organ"}

# nosode.category ↔ etiology.agent_type mapping
_CATEGORY_MAP = {
    "bacteria_cocci": "bacteria_cocci",
    "bacteria_bacilli": "bacteria_bacilli",
    "virus": "virus",
    "protozoa_helminths_fungi": "parasite_fungi",
    "parasite_fungi": "protozoa_helminths_fungi",
}


# organ_preparations.disease_category → therapeutic_index.disease_system
# Keyword-based fuzzy matching (organ categories are more granular than disease_systems)
_ORGAN_KEYWORDS_TO_DS: list[tuple[str, str]] = [
    ("кож", "Заболевания Кожи"),
    ("нейродермит", "Заболевания Кожи"),
    ("экзема", "Заболевания Кожи"),
    ("псориаз", "Заболевания Кожи"),
    ("склеродерм", "Заболевания Кожи"),
    ("молочн", "Заболевания Молочных Желез"),
    ("женск", "Заболевания Мочеполовой Системы"),
    ("урогенитальн", "Заболевания Мочеполовой Системы"),
    ("мужск", "Заболевания Мочеполовой Системы"),
    ("почек", "Заболевания Мочеполовой Системы"),
    ("зрения", "Заболевания Органов Зрения"),
    ("цветовосприят", "Заболевания Органов Зрения"),
    ("сердца", "Заболевания Сердечно-сосудистой Системы"),
    ("аорт", "Заболевания Сердечно-сосудистой Системы"),
    ("артериальн", "Заболевания Сердечно-сосудистой Системы"),
    ("венозн", "Заболевания Сердечно-сосудистой Системы"),
    ("кровообращен", "Заболевания Сердечно-сосудистой Системы"),
    ("щитовидн", "Заболевания Щитовидной Железы"),
    ("тимус", "Заболевания Щитовидной Железы"),
    ("гипоталамо", "Заболевания Щитовидной Железы"),
    ("бронхолег", "Заболеваний Органов И Систем"),
    ("дыхательн", "Заболеваний Органов И Систем"),
    ("обоняни", "Заболеваний Органов И Систем"),
    ("зубов", "Заболевания Слизистых Полости Рта"),
    ("полости рта", "Заболевания Слизистых Полости Рта"),
    ("стоматит", "Заболевания Слизистых Полости Рта"),
    ("вкусов", "Заболевания Слизистых Полости Рта"),
    ("слюн", "Заболевания Слизистых Полости Рта"),
    ("пищеварител", "Заболевания Пищеварительной Системы"),
    ("двенадцатиперстн", "Заболевания Пищеварительной Системы"),
    ("толстого кишечник", "Заболевания Пищеварительной Системы"),
    ("тонкого кишечник", "Заболевания Пищеварительной Системы"),
    ("прямой кишк", "Заболевания Пищеварительной Системы"),
    ("поджелудочн", "Заболевания Пищеварительной Системы"),
    ("дисбактериоз", "Заболевания Пищеварительной Системы"),
    ("гепатобилиарн", "Заболевания Печени, Желчного Пузыря"),
    ("печен", "Заболевания Печени, Желчного Пузыря"),
    ("суставов", "Заболевания Опорно-двигательной Системы"),
    ("суставы", "Заболевания Опорно-двигательной Системы"),
    ("позвоночник", "Заболевания Опорно-двигательной Системы"),
    ("мышц", "Заболевания Опорно-двигательной Системы"),
    ("височно", "Заболевания Опорно-двигательной Системы"),
    ("тендовагинит", "Заболевания Опорно-двигательной Системы"),
    ("артроз", "Заболевания Опорно-двигательной Системы"),
    ("нервов", "Заболевания Нервной Системы"),
    ("мозга", "Заболевания Нервной Системы"),
    ("мозговых", "Заболевания Нервной Системы"),
    ("головного", "Заболевания Нервной Системы"),
    ("грудного отдела", "Заболевания Нервной Системы"),
    ("пояснично", "Заболевания Нервной Системы"),
    ("ганглиев", "Заболевания Нервной Системы"),
    ("периферическ", "Заболевания Нервной Системы"),
    ("паркинсон", "Заболевания Нервной Системы"),
    ("селезенк", "Заболевания Селезенки"),
    ("костного мозга", "Заболевания Костного Мозга"),
]


def _match_organ_to_disease_system(disease_category: str) -> str | None:
    """Match organ disease_category to therapeutic_index disease_system via keywords."""
    cat_lower = disease_category.lower()
    for keyword, ds in _ORGAN_KEYWORDS_TO_DS:
        if keyword.lower() in cat_lower:
            return ds
    return None


async def _resolve_remedies(db, remedy_names: list[str]) -> list[dict]:
    """Resolve remedy names → relation dicts via direct name match."""
    result = []
    seen_ids: set[int] = set()
    for name in remedy_names:
        matched = await db.execute_fetchall(
            "SELECT id, name_lat FROM remedies WHERE name_lat = ? COLLATE NOCASE",
            (name,),
        )
        if matched and matched[0]["id"] not in seen_ids:
            seen_ids.add(matched[0]["id"])
            result.append({"type": "remedy", "id": matched[0]["id"], "name": matched[0]["name_lat"]})
        elif not matched:
            result.append({"type": "remedy", "id": None, "name": name})
    return result


@router.get("/handbook/relations/{entity_type}/{entity_id}")
async def get_relations(entity_type: str, entity_id: int):
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"Unknown entity_type: {entity_type}")

    db = await get_db()
    center = None
    relations: list[dict] = []

    if entity_type == "condition":
        rows = await db.execute_fetchall(
            "SELECT id, condition_name, remedies_list FROM therapeutic_index WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Condition not found")
        center = {"type": "condition", "id": rows[0]["id"], "name": rows[0]["condition_name"]}
        raw_names = json.loads(rows[0]["remedies_list"])
        relations.extend(await _resolve_remedies(db, raw_names))

    elif entity_type == "remedy":
        rows = await db.execute_fetchall(
            "SELECT id, name_lat FROM remedies WHERE id = ?", (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Remedy not found")
        center = {"type": "remedy", "id": rows[0]["id"], "name": rows[0]["name_lat"]}
        name_lat = rows[0]["name_lat"]

        # Find conditions that reference this remedy
        cond_rows = await db.execute_fetchall(
            "SELECT id, condition_name FROM therapeutic_index "
            "WHERE remedies_list LIKE ? COLLATE NOCASE LIMIT 10",
            (f'%{name_lat}%',),
        )
        for c in cond_rows:
            relations.append({"type": "condition", "id": c["id"], "name": c["condition_name"]})

    elif entity_type == "nosode":
        rows = await db.execute_fetchall(
            "SELECT id, name_lat, name_rus, category FROM nosodes WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Nosode not found")
        center = {"type": "nosode", "id": rows[0]["id"], "name": rows[0]["name_lat"]}

        # 1. Related etiology via matching category (existing logic)
        cat = rows[0]["category"]
        mapped_type = _CATEGORY_MAP.get(cat)
        if mapped_type:
            etio_rows = await db.execute_fetchall(
                "SELECT id, agent_name FROM etiology WHERE agent_type = ? LIMIT 10",
                (mapped_type,),
            )
            for e in etio_rows:
                relations.append({"type": "etiology", "id": e["id"], "name": e["agent_name"]})

        # 2. Find conditions via disease_system (nosode name → etiology → disease_system → conditions)
        name_lat = rows[0]["name_lat"]
        # Extract first word as stem for matching (e.g. "Streptococcinum" → "Streptococ")
        name_stem = name_lat.split()[0][:10] if name_lat else ""
        disease_systems: set[str] = set()
        if len(name_stem) >= 4:
            etio_ds = await db.execute_fetchall(
                "SELECT DISTINCT disease_system FROM etiology "
                "WHERE agent_name LIKE ? AND disease_system IS NOT NULL LIMIT 5",
                (f"%{name_stem}%",),
            )
            for e in etio_ds:
                disease_systems.add(e["disease_system"])
        if disease_systems:
            placeholders = ",".join("?" * len(disease_systems))
            cond_rows = await db.execute_fetchall(
                f"SELECT id, condition_name, remedies_list FROM therapeutic_index "
                f"WHERE disease_system IN ({placeholders}) ORDER BY condition_name LIMIT 10",
                list(disease_systems),
            )
            seen_remedy_names: list[str] = []
            for c in cond_rows:
                relations.append({"type": "condition", "id": c["id"], "name": c["condition_name"]})
                for rn in json.loads(c["remedies_list"]):
                    if rn not in seen_remedy_names:
                        seen_remedy_names.append(rn)
            relations.extend(await _resolve_remedies(db, seen_remedy_names[:10]))

    elif entity_type == "etiology":
        rows = await db.execute_fetchall(
            "SELECT id, agent_name, agent_type, disease_system FROM etiology WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Etiology not found")
        center = {"type": "etiology", "id": rows[0]["id"], "name": rows[0]["agent_name"]}

        # 1. Related nosodes via matching agent_type (existing logic)
        agent_type = rows[0]["agent_type"]
        mapped_cat = _CATEGORY_MAP.get(agent_type)
        if mapped_cat:
            nos_rows = await db.execute_fetchall(
                "SELECT id, name_lat FROM nosodes WHERE category = ? LIMIT 10",
                (mapped_cat,),
            )
            for n in nos_rows:
                relations.append({"type": "nosode", "id": n["id"], "name": n["name_lat"]})

        # 2. Conditions via disease_system (direct link)
        ds = rows[0]["disease_system"]
        if ds:
            cond_rows = await db.execute_fetchall(
                "SELECT id, condition_name, remedies_list FROM therapeutic_index "
                "WHERE disease_system = ? ORDER BY condition_name LIMIT 15",
                (ds,),
            )
            seen_remedy_names: list[str] = []
            for c in cond_rows:
                relations.append({"type": "condition", "id": c["id"], "name": c["condition_name"]})
                for rn in json.loads(c["remedies_list"]):
                    if rn not in seen_remedy_names:
                        seen_remedy_names.append(rn)
            relations.extend(await _resolve_remedies(db, seen_remedy_names[:10]))

    elif entity_type == "organ":
        rows = await db.execute_fetchall(
            "SELECT id, organ_name, disease_category FROM organ_preparations WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Organ preparation not found")
        center = {"type": "organ", "id": rows[0]["id"], "name": rows[0]["organ_name"]}

        # 1. Related organs in the same disease category (existing logic)
        cat = rows[0]["disease_category"]
        if cat:
            cat_rows = await db.execute_fetchall(
                "SELECT id, organ_name FROM organ_preparations "
                "WHERE disease_category = ? AND id != ? LIMIT 10",
                (cat, entity_id),
            )
            for o in cat_rows:
                relations.append({"type": "organ", "id": o["id"], "name": o["organ_name"]})

        # 2. Conditions via disease_system (fuzzy match disease_category → disease_system)
        matched_ds = _match_organ_to_disease_system(cat) if cat else None
        if matched_ds:
            cond_rows = await db.execute_fetchall(
                "SELECT id, condition_name, remedies_list FROM therapeutic_index "
                "WHERE disease_system = ? ORDER BY condition_name LIMIT 10",
                (matched_ds,),
            )
            seen_remedy_names: list[str] = []
            for c in cond_rows:
                relations.append({"type": "condition", "id": c["id"], "name": c["condition_name"]})
                for rn in json.loads(c["remedies_list"]):
                    if rn not in seen_remedy_names:
                        seen_remedy_names.append(rn)
            relations.extend(await _resolve_remedies(db, seen_remedy_names[:10]))

    return {"center": center, "relations": relations}


# ─── Stats ────────────────────────────────────────────────────────

@router.get("/handbook/stats")
async def handbook_stats():
    db = await get_db()
    tables = {
        "conditions": "SELECT COUNT(*) as cnt FROM therapeutic_index",
        "remedies": "SELECT COUNT(*) as cnt FROM remedies",
        "symptoms": "SELECT COUNT(*) as cnt FROM remedy_symptoms",
        "nosodes": "SELECT COUNT(*) as cnt FROM nosodes",
        "etiology": "SELECT COUNT(*) as cnt FROM etiology",
        "organs": "SELECT COUNT(*) as cnt FROM organ_preparations",
    }
    stats = {}
    for key, query in tables.items():
        try:
            row = await db.execute_fetchall(query)
            stats[key] = row[0]["cnt"]
        except Exception:
            stats[key] = 0

    stats["total"] = sum(stats.values())
    return stats
