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


# ─── Toxic Substances ─────────────────────────────────────────────

@router.get("/handbook/toxic")
async def list_toxic_substances(
    category: str | None = Query(None, description="Filter: heavy_metal, pesticide, etc."),
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
        f"SELECT id, name_rus, name_eng, category, description, source_page "
        f"FROM toxic_substances {where} ORDER BY category, name_rus LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    total = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM toxic_substances {where}", params,
    )

    cats = await db.execute_fetchall(
        "SELECT DISTINCT category FROM toxic_substances WHERE category IS NOT NULL ORDER BY category"
    )

    return {
        "results": [dict(r) for r in rows],
        "total": total[0]["cnt"],
        "categories": [c["category"] for c in cats],
    }


# ─── Pathomorphological Nosodes ──────────────────────────────────

@router.get("/handbook/pathomorphological")
async def list_pathomorphological(
    category: str | None = Query(None, description="Filter by disease category"),
    limit: int = Query(300, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()

    where = ""
    params: list = []
    if category:
        where = "WHERE disease_category = ?"
        params.append(category)

    rows = await db.execute_fetchall(
        f"SELECT id, condition_name, condition_name_lat, disease_category, source_page "
        f"FROM pathomorphological_nosodes {where} ORDER BY disease_category, condition_name LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    total = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM pathomorphological_nosodes {where}", params,
    )

    cats = await db.execute_fetchall(
        "SELECT DISTINCT disease_category FROM pathomorphological_nosodes "
        "WHERE disease_category IS NOT NULL ORDER BY disease_category"
    )

    return {
        "results": [dict(r) for r in rows],
        "total": total[0]["cnt"],
        "categories": [c["disease_category"] for c in cats],
    }


# ─── Relations (cross-entity) ────────────────────────────────────

ENTITY_TYPES = {"condition", "remedy", "nosode", "etiology", "organ", "toxic", "pathomorphological"}

# nosode.category ↔ etiology.agent_type mapping
_CATEGORY_MAP = {
    "bacteria_cocci": "bacteria_cocci",
    "bacteria_bacilli": "bacteria_bacilli",
    "virus": "virus",
    "protozoa_helminths_fungi": "parasite_fungi",
    "parasite_fungi": "protozoa_helminths_fungi",
}

# nosode_remedies.disease_system → etiology.disease_system mapping
_NR_DS_TO_ETIO_DS: dict[str, list[str]] = {
    "Нервная система": ["Заболевания Нервной Системы"],
    "Сердечно-сосудистая система": ["Заболевания Сердечно-сосудистой Системы"],
    "Дыхательная система и ЛОР": ["Заболеваний Органов И Систем"],
    "Пищеварительная система и печень": [
        "Заболевания Пищеварительной Системы",
        "Заболевания Печени, Желчного Пузыря",
    ],
    "Опорно-двигательная система": ["Заболевания Опорно-двигательной Системы"],
    "Эндокринная и иммунная системы": [
        "Заболевания Щитовидной Железы",
        "Заболевания Надпочечников",
    ],
    "Мочеполовая система": ["Заболевания Мочеполовой Системы"],
    "Кожа": ["Заболевания Кожи"],
}

# Reverse: etiology.disease_system → nosode_remedies.disease_system
_ETIO_DS_TO_NR_DS: dict[str, str] = {}
for _nr_ds, _etio_ds_list in _NR_DS_TO_ETIO_DS.items():
    for _etio_ds in _etio_ds_list:
        _ETIO_DS_TO_NR_DS[_etio_ds] = _nr_ds


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
    ("слух", "Заболевания Органов Слуха"),
    ("оболочек мозга", "Заболевания Нервной Системы"),
    ("черепно-мозговых", "Заболевания Нервной Системы"),
    ("различных отделов", "Заболевания Нервной Системы"),
    ("соединительной ткани", "Заболевания Кожи"),
    ("струмэктом", "Заболевания Щитовидной Железы"),
    ("миндалин", "Заболевания Миндалин И Лимфоузлов"),
    ("лимфоузл", "Заболевания Миндалин И Лимфоузлов"),
    ("околоушн", "Заболевания Околоушных Желез"),
    ("развития", "Заболеваний Органов И Систем"),
    ("гиперплаз", "Заболеваний Органов И Систем"),
    ("диабет", "Заболевания Сердечно-сосудистой Системы"),
    ("периартериит", "Заболевания Сердечно-сосудистой Системы"),
]


def _match_organ_to_disease_system(disease_category: str) -> str | None:
    """Match organ disease_category to therapeutic_index disease_system via keywords."""
    cat_lower = disease_category.lower()
    for keyword, ds in _ORGAN_KEYWORDS_TO_DS:
        if keyword.lower() in cat_lower:
            return ds
    return None


async def _resolve_remedies(db, remedy_names: list[str]) -> list[dict]:
    """Resolve remedy names → relation dicts via remedies + remedy_aliases. Skip unresolved."""
    result = []
    seen_ids: set[int] = set()
    for name in remedy_names:
        # 1. Direct match in remedies
        matched = await db.execute_fetchall(
            "SELECT id, name_lat FROM remedies WHERE name_lat = ? COLLATE NOCASE",
            (name,),
        )
        # 2. Via remedy_aliases → canonical remedy
        if not matched:
            matched = await db.execute_fetchall(
                "SELECT r.id, r.name_lat FROM remedy_aliases ra "
                "JOIN remedies r ON r.id = ra.canonical_remedy_id "
                "WHERE ra.alias = ? COLLATE NOCASE",
                (name,),
            )
        if matched and matched[0]["id"] not in seen_ids:
            seen_ids.add(matched[0]["id"])
            result.append({"type": "remedy", "id": matched[0]["id"], "name": matched[0]["name_lat"]})
        # Skip unresolved — no id:null entries
    return result


@router.get("/handbook/relations/{entity_type}/{entity_id}")
async def get_relations(entity_type: str, entity_id: int):
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"Unknown entity_type: {entity_type}")

    db = await get_db()
    center = None
    relations: list[dict] = []
    extra: dict = {}  # Additional data (nosode_combos, incompatible_remedies, etc.)

    if entity_type == "condition":
        rows = await db.execute_fetchall(
            "SELECT id, condition_name, remedies_list, disease_system FROM therapeutic_index WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Condition not found")
        center = {"type": "condition", "id": rows[0]["id"], "name": rows[0]["condition_name"]}
        raw_names = json.loads(rows[0]["remedies_list"])
        relations.extend(await _resolve_remedies(db, raw_names))

        # Etiology via disease_system
        ds = rows[0]["disease_system"]
        if ds:
            etio_rows = await db.execute_fetchall(
                "SELECT id, agent_name FROM etiology WHERE disease_system = ? "
                "ORDER BY agent_name LIMIT 15",
                (ds,),
            )
            for e in etio_rows:
                relations.append({"type": "etiology", "id": e["id"], "name": e["agent_name"]})

        # Nosodes via nosode_remedies.disease_system (map etiology DS → NR DS)
        nr_ds = _ETIO_DS_TO_NR_DS.get(ds) if ds else None
        if nr_ds:
            nr_rows = await db.execute_fetchall(
                "SELECT DISTINCT nr.nosode_name, nr.nosode_id "
                "FROM nosode_remedies nr WHERE nr.disease_system = ? "
                "ORDER BY nr.nosode_name",
                (nr_ds,),
            )
            seen_nosode_ids: set[int | None] = set()
            for nr in nr_rows:
                nid = nr["nosode_id"]
                if nid and nid not in seen_nosode_ids:
                    seen_nosode_ids.add(nid)
                    relations.append({"type": "nosode", "id": nid, "name": nr["nosode_name"]})

        # Condition-specific nosode combinations from Table 17 (condition_nosodes)
        cn_rows = await db.execute_fetchall(
            "SELECT nosode_names, patient_count, percentage, is_primary "
            "FROM condition_nosodes WHERE condition_id = ? "
            "ORDER BY percentage DESC",
            (entity_id,),
        )
        if not cn_rows:
            # Try by condition_name (fuzzy)
            cond_name = rows[0]["condition_name"]
            cn_rows = await db.execute_fetchall(
                "SELECT nosode_names, patient_count, percentage, is_primary "
                "FROM condition_nosodes WHERE condition_name = ? COLLATE NOCASE "
                "ORDER BY percentage DESC",
                (cond_name,),
            )
        if cn_rows:
            nosode_combos = []
            for cn in cn_rows:
                nosode_combos.append({
                    "nosode_names": cn["nosode_names"],
                    "patient_count": cn["patient_count"],
                    "percentage": cn["percentage"],
                    "is_primary": bool(cn["is_primary"]),
                })
            extra["nosode_combinations"] = nosode_combos

    elif entity_type == "remedy":
        rows = await db.execute_fetchall(
            "SELECT id, name_lat FROM remedies WHERE id = ?", (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Remedy not found")
        center = {"type": "remedy", "id": rows[0]["id"], "name": rows[0]["name_lat"]}
        name_lat = rows[0]["name_lat"]

        # Conditions that reference this remedy
        cond_rows = await db.execute_fetchall(
            "SELECT id, condition_name FROM therapeutic_index "
            "WHERE remedies_list LIKE ? COLLATE NOCASE "
            "ORDER BY condition_name",
            (f'%{name_lat}%',),
        )
        for c in cond_rows:
            relations.append({"type": "condition", "id": c["id"], "name": c["condition_name"]})

        # Nosodes that pair with this remedy (from nosode_remedies)
        # Search by remedy_id, exact name, or first word of name (Hyoscyamus niger → Hyoscyamus)
        first_word = name_lat.split()[0] if name_lat else ""
        nr_rows = await db.execute_fetchall(
            "SELECT DISTINCT nr.nosode_name, nr.nosode_id, nr.effectiveness, nr.disease_system "
            "FROM nosode_remedies nr "
            "WHERE nr.remedy_id = ? OR nr.remedy_name = ? COLLATE NOCASE "
            "   OR nr.remedy_name LIKE ? COLLATE NOCASE "
            "ORDER BY nr.effectiveness DESC",
            (entity_id, name_lat, f"{first_word}%"),
        )
        seen_nosode_names: set[str] = set()
        for nr in nr_rows:
            nn = nr["nosode_name"]
            if nn not in seen_nosode_names:
                seen_nosode_names.add(nn)
                relations.append({
                    "type": "nosode", "id": nr["nosode_id"], "name": nn,
                    "effectiveness": nr["effectiveness"],
                    "disease_system": nr["disease_system"],
                })

        # Incompatible remedies from Table 18 (bidirectional lookup)
        incompat_rows = await db.execute_fetchall(
            "SELECT incompatible_remedy_name AS name, incompatible_remedy_id AS rid "
            "FROM remedy_incompatibility WHERE remedy_id = ? "
            "UNION "
            "SELECT remedy_name AS name, remedy_id AS rid "
            "FROM remedy_incompatibility WHERE incompatible_remedy_id = ? "
            "ORDER BY 1",
            (entity_id, entity_id),
        )
        # Also try by name (most remedy_ids are NULL)
        if not incompat_rows:
            first_word = name_lat.split()[0] if name_lat else ""
            incompat_rows = await db.execute_fetchall(
                "SELECT incompatible_remedy_name AS name, incompatible_remedy_id AS rid "
                "FROM remedy_incompatibility "
                "WHERE remedy_name = ? COLLATE NOCASE OR remedy_name LIKE ? COLLATE NOCASE "
                "UNION "
                "SELECT remedy_name AS name, remedy_id AS rid "
                "FROM remedy_incompatibility "
                "WHERE incompatible_remedy_name = ? COLLATE NOCASE "
                "   OR incompatible_remedy_name LIKE ? COLLATE NOCASE "
                "ORDER BY 1",
                (name_lat, f"{first_word}%", name_lat, f"{first_word}%"),
            )
        if incompat_rows:
            extra["incompatible_remedies"] = [
                {"name": ir["name"], "id": ir["rid"]} for ir in incompat_rows
            ]

    elif entity_type == "nosode":
        rows = await db.execute_fetchall(
            "SELECT id, name_lat, name_rus, category FROM nosodes WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Nosode not found")
        center = {"type": "nosode", "id": rows[0]["id"], "name": rows[0]["name_lat"]}

        # 1. DIRECT: Remedies from nosode_remedies (with effectiveness!)
        nr_rows = await db.execute_fetchall(
            "SELECT remedy_name, remedy_id, effectiveness, disease_system "
            "FROM nosode_remedies WHERE nosode_id = ? "
            "ORDER BY effectiveness DESC",
            (entity_id,),
        )

        # Also try by nosode_name (for nosodes not resolved by ID in nosode_remedies)
        if not nr_rows:
            name_lat = rows[0]["name_lat"]
            nr_rows = await db.execute_fetchall(
                "SELECT remedy_name, remedy_id, effectiveness, disease_system "
                "FROM nosode_remedies WHERE nosode_name LIKE ? COLLATE NOCASE "
                "ORDER BY effectiveness DESC",
                (f"%{name_lat.split()[0]}%",),
            )

        # Deduplicate by remedy_name, keep highest effectiveness
        seen_remedy_names: set[str] = set()
        for nr in nr_rows:
            rn = nr["remedy_name"]
            if rn not in seen_remedy_names:
                seen_remedy_names.add(rn)
                relations.append({
                    "type": "remedy", "id": nr["remedy_id"], "name": rn,
                    "effectiveness": nr["effectiveness"],
                    "disease_system": nr["disease_system"],
                })

        # 2. SPECIFIC etiology: find agents whose name matches this nosode
        name_lat = rows[0]["name_lat"]
        nosode_stem = name_lat.split()[0][:8] if name_lat else ""
        if len(nosode_stem) >= 4:
            etio_rows = await db.execute_fetchall(
                "SELECT id, agent_name FROM etiology "
                "WHERE agent_name LIKE ? COLLATE NOCASE "
                "ORDER BY agent_name",
                (f"%{nosode_stem}%",),
            )
            seen_etio_names: set[str] = set()
            for e in etio_rows:
                if e["agent_name"] not in seen_etio_names:
                    seen_etio_names.add(e["agent_name"])
                    relations.append({"type": "etiology", "id": e["id"], "name": e["agent_name"]})

        # 3. SPECIFIC conditions from condition_nosodes (Table 17)
        # Find conditions where nosode_names contains this nosode's name
        cn_rows = await db.execute_fetchall(
            "SELECT condition_name, condition_id, nosode_names, percentage "
            "FROM condition_nosodes "
            "WHERE nosode_names LIKE ? COLLATE NOCASE "
            "ORDER BY percentage DESC",
            (f"%{nosode_stem}%",),
        )
        seen_cond_ids: set[int | None] = set()
        for cn in cn_rows:
            cid = cn["condition_id"]
            if cid and cid not in seen_cond_ids:
                seen_cond_ids.add(cid)
                relations.append({"type": "condition", "id": cid, "name": cn["condition_name"]})

    elif entity_type == "etiology":
        rows = await db.execute_fetchall(
            "SELECT id, agent_name, agent_type, disease_system FROM etiology WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Etiology not found")
        center = {"type": "etiology", "id": rows[0]["id"], "name": rows[0]["agent_name"]}
        agent_name = rows[0]["agent_name"]
        agent_type = rows[0]["agent_type"]
        ds = rows[0]["disease_system"]

        # 1. Remedies via nosode_remedies (agent_name ~ nosode_name)
        agent_stem = agent_name.split()[0][:8] if agent_name else ""
        if len(agent_stem) >= 4:
            nr_rows = await db.execute_fetchall(
                "SELECT remedy_name, remedy_id, effectiveness, disease_system "
                "FROM nosode_remedies WHERE nosode_name LIKE ? COLLATE NOCASE "
                "ORDER BY effectiveness DESC",
                (f"%{agent_stem}%",),
            )
            seen_remedy_names: set[str] = set()
            for nr in nr_rows:
                rn = nr["remedy_name"]
                if rn not in seen_remedy_names:
                    seen_remedy_names.add(rn)
                    relations.append({
                        "type": "remedy", "id": nr["remedy_id"], "name": rn,
                        "effectiveness": nr["effectiveness"],
                        "disease_system": nr["disease_system"],
                    })

        # 2. Related nosodes via agent_type
        mapped_cat = _CATEGORY_MAP.get(agent_type)
        if mapped_cat:
            nos_rows = await db.execute_fetchall(
                "SELECT id, name_lat FROM nosodes WHERE category = ? "
                "ORDER BY name_lat LIMIT 10",
                (mapped_cat,),
            )
            for n in nos_rows:
                relations.append({"type": "nosode", "id": n["id"], "name": n["name_lat"]})

        # 3. Conditions via disease_system
        if ds:
            cond_rows = await db.execute_fetchall(
                "SELECT id, condition_name FROM therapeutic_index "
                "WHERE disease_system = ? ORDER BY condition_name LIMIT 15",
                (ds,),
            )
            for c in cond_rows:
                relations.append({"type": "condition", "id": c["id"], "name": c["condition_name"]})

    elif entity_type == "organ":
        rows = await db.execute_fetchall(
            "SELECT id, organ_name, disease_category FROM organ_preparations WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Organ preparation not found")
        center = {"type": "organ", "id": rows[0]["id"], "name": rows[0]["organ_name"]}

        # 1. Related organs in the same category
        cat = rows[0]["disease_category"]
        if cat:
            cat_rows = await db.execute_fetchall(
                "SELECT id, organ_name FROM organ_preparations "
                "WHERE disease_category = ? AND id != ? "
                "ORDER BY organ_name LIMIT 10",
                (cat, entity_id),
            )
            for o in cat_rows:
                relations.append({"type": "organ", "id": o["id"], "name": o["organ_name"]})

        # 2. Conditions via fuzzy disease_category → disease_system match
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

        # 3. Remedies via nosode_remedies (organ category → NR disease_system)
        nr_ds = _ETIO_DS_TO_NR_DS.get(matched_ds) if matched_ds else None
        if nr_ds:
            nr_rows = await db.execute_fetchall(
                "SELECT DISTINCT remedy_name, remedy_id, effectiveness "
                "FROM nosode_remedies WHERE disease_system = ? "
                "ORDER BY effectiveness DESC LIMIT 10",
                (nr_ds,),
            )
            seen_remedy_names_nr: set[str] = set()
            for nr in nr_rows:
                rn = nr["remedy_name"]
                if rn not in seen_remedy_names_nr:
                    seen_remedy_names_nr.add(rn)
                    relations.append({
                        "type": "remedy", "id": nr["remedy_id"], "name": rn,
                        "effectiveness": nr["effectiveness"],
                    })

    elif entity_type == "toxic":
        rows = await db.execute_fetchall(
            "SELECT id, name_rus, name_eng, category FROM toxic_substances WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Toxic substance not found")
        center = {"type": "toxic", "id": rows[0]["id"], "name": rows[0]["name_rus"]}

        # Related toxic substances in the same category
        cat = rows[0]["category"]
        if cat:
            cat_rows = await db.execute_fetchall(
                "SELECT id, name_rus FROM toxic_substances "
                "WHERE category = ? AND id != ? ORDER BY name_rus LIMIT 15",
                (cat, entity_id),
            )
            for t in cat_rows:
                relations.append({"type": "toxic", "id": t["id"], "name": t["name_rus"]})

    elif entity_type == "pathomorphological":
        rows = await db.execute_fetchall(
            "SELECT id, condition_name, condition_name_lat, disease_category "
            "FROM pathomorphological_nosodes WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Pathomorphological nosode not found")
        center = {"type": "pathomorphological", "id": rows[0]["id"], "name": rows[0]["condition_name"]}

        # Related pathomorphological nosodes in the same disease category
        cat = rows[0]["disease_category"]
        if cat:
            cat_rows = await db.execute_fetchall(
                "SELECT id, condition_name FROM pathomorphological_nosodes "
                "WHERE disease_category = ? AND id != ? ORDER BY condition_name LIMIT 15",
                (cat, entity_id),
            )
            for p in cat_rows:
                relations.append({"type": "pathomorphological", "id": p["id"], "name": p["condition_name"]})

    # Sort relations by type, then by name alphabetically
    def _sort_key(r: dict) -> tuple:
        type_order = {"remedy": 0, "nosode": 1, "condition": 2, "etiology": 3, "organ": 4, "toxic": 5, "pathomorphological": 6}
        return (type_order.get(r["type"], 9), r.get("name", ""))

    relations.sort(key=_sort_key)

    result = {"center": center, "relations": relations}
    result.update(extra)
    return result


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
        "nosode_remedies": "SELECT COUNT(*) as cnt FROM nosode_remedies",
        "condition_nosodes": "SELECT COUNT(*) as cnt FROM condition_nosodes",
        "remedy_incompatibility": "SELECT COUNT(*) as cnt FROM remedy_incompatibility",
        "remedy_aliases": "SELECT COUNT(*) as cnt FROM remedy_aliases",
        "toxic_substances": "SELECT COUNT(*) as cnt FROM toxic_substances",
        "pathomorphological_nosodes": "SELECT COUNT(*) as cnt FROM pathomorphological_nosodes",
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
