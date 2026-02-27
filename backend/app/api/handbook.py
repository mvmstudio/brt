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
        "SELECT id, condition_name, remedies_list, source_page, description, content_source "
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
        "SELECT id, condition_name, remedies_list, source_page, description, content_source "
        "FROM therapeutic_index WHERE id = ?",
        (condition_id,),
    )
    if not rows:
        raise HTTPException(404, "Condition not found")

    d = dict(rows[0])
    remedy_names = json.loads(d.pop("remedies_list"))
    d["remedies"] = remedy_names

    # Enrich: resolve remedies via alias table
    enriched = []
    for name in remedy_names:
        matched = await db.execute_fetchall(
            "SELECT r.id, r.name_lat, r.name_rus, r.summary "
            "FROM remedy_aliases ra JOIN remedies r ON r.id = ra.canonical_remedy_id "
            "WHERE ra.alias = ? COLLATE NOCASE",
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
        "SELECT id, name_lat, name_rus, source_pages, summary, content_source FROM remedies WHERE id = ?",
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

    # Related conditions via alias table
    condition_rows = await db.execute_fetchall(
        "SELECT DISTINCT ti.id, ti.condition_name "
        "FROM therapeutic_index ti, remedy_aliases ra "
        "WHERE ra.canonical_remedy_id = ? "
        "AND ti.remedies_list LIKE '%' || ra.alias || '%' "
        "ORDER BY ti.condition_name",
        (remedy_id,),
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
        f"SELECT id, number, name_lat, name_rus, category, source_page, description, content_source, remedies_list "
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

    results = []
    for r in rows:
        d = dict(r)
        if d.get("remedies_list"):
            d["remedies_list"] = json.loads(d["remedies_list"])
        results.append(d)

    return {
        "results": results,
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
        f"SELECT id, disease_system, agent_type, agent_name, agent_name_rus, source_page, description, content_source, remedies_list "
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

    results = []
    for r in rows:
        d = dict(r)
        if d.get("remedies_list"):
            d["remedies_list"] = json.loads(d["remedies_list"])
        results.append(d)

    return {
        "results": results,
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
        f"SELECT id, disease_category, organ_name, organ_name_lat, manufacturer, source_page, description, content_source, remedies_list "
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

    results = []
    for r in rows:
        d = dict(r)
        if d.get("remedies_list"):
            d["remedies_list"] = json.loads(d["remedies_list"])
        results.append(d)

    return {
        "results": results,
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


def _parse_remedies(raw: str | None) -> set[str]:
    """Parse remedies_list JSON → lowercase set."""
    if not raw:
        return set()
    try:
        return {n.lower() for n in json.loads(raw)}
    except (json.JSONDecodeError, TypeError):
        return set()


async def _resolve_remedies(db, remedy_names: list[str]) -> list[dict]:
    """Resolve remedy names → relation dicts via alias table."""
    result = []
    seen_ids: set[int] = set()
    for name in remedy_names:
        matched = await db.execute_fetchall(
            "SELECT r.id, r.name_lat FROM remedy_aliases ra "
            "JOIN remedies r ON r.id = ra.canonical_remedy_id "
            "WHERE ra.alias = ? COLLATE NOCASE",
            (name,),
        )
        if matched and matched[0]["id"] not in seen_ids:
            seen_ids.add(matched[0]["id"])
            result.append({"type": "remedy", "id": matched[0]["id"], "name": matched[0]["name_lat"]})
        elif not matched:
            result.append({"type": "remedy", "id": None, "name": name})
    return result


async def _shared_remedy_entities(
    db, my_remedies: set[str], table: str, name_col: str,
    entity_type: str, exclude_id: int | None = None, limit: int = 10,
) -> list[dict]:
    """Find entities in table sharing remedies, ranked by overlap count."""
    if not my_remedies:
        return []
    rows = await db.execute_fetchall(
        f"SELECT id, {name_col}, remedies_list FROM {table} WHERE remedies_list IS NOT NULL"
    )
    scored = []
    for r in rows:
        if exclude_id and r["id"] == exclude_id:
            continue
        their = _parse_remedies(r["remedies_list"])
        overlap = len(my_remedies & their)
        if overlap > 0:
            scored.append((overlap, r["id"], r[name_col]))
    scored.sort(key=lambda x: -x[0])
    return [{"type": entity_type, "id": s[1], "name": s[2]} for s in scored[:limit]]


async def _remedy_reverse_lookup(db, entity_id: int, table: str, name_col: str, entity_type: str) -> list[dict]:
    """Find entities whose remedies_list contains any alias of remedy_id."""
    aliases = await db.execute_fetchall(
        "SELECT alias FROM remedy_aliases WHERE canonical_remedy_id = ?", (entity_id,),
    )
    alias_list = [a["alias"] for a in aliases]
    if not alias_list:
        return []
    rows = await db.execute_fetchall(
        f"SELECT id, {name_col}, remedies_list FROM {table} WHERE remedies_list IS NOT NULL"
    )
    result = []
    alias_lower = {a.lower() for a in alias_list}
    for r in rows:
        rl = _parse_remedies(r["remedies_list"])
        if alias_lower & rl:
            result.append({"type": entity_type, "id": r["id"], "name": r[name_col]})
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
        my_remedies = _parse_remedies(rows[0]["remedies_list"])

        # Direct remedies
        relations.extend(await _resolve_remedies(db, raw_names))
        # Cross-entity via shared remedies
        relations.extend(await _shared_remedy_entities(db, my_remedies, "nosodes", "name_lat", "nosode"))
        relations.extend(await _shared_remedy_entities(db, my_remedies, "etiology", "agent_name", "etiology"))
        relations.extend(await _shared_remedy_entities(db, my_remedies, "organ_preparations", "organ_name", "organ"))

    elif entity_type == "remedy":
        rows = await db.execute_fetchall(
            "SELECT id, name_lat FROM remedies WHERE id = ?", (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Remedy not found")
        center = {"type": "remedy", "id": rows[0]["id"], "name": rows[0]["name_lat"]}

        # All entity types that reference this remedy (top-10 each)
        for tbl, col, etype in [
            ("therapeutic_index", "condition_name", "condition"),
            ("nosodes", "name_lat", "nosode"),
            ("etiology", "agent_name", "etiology"),
            ("organ_preparations", "organ_name", "organ"),
        ]:
            found = await _remedy_reverse_lookup(db, entity_id, tbl, col, etype)
            relations.extend(found[:10])

    elif entity_type == "nosode":
        rows = await db.execute_fetchall(
            "SELECT id, name_lat, remedies_list, category FROM nosodes WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Nosode not found")
        center = {"type": "nosode", "id": rows[0]["id"], "name": rows[0]["name_lat"]}
        raw_names = json.loads(rows[0]["remedies_list"]) if rows[0]["remedies_list"] else []
        my_remedies = _parse_remedies(rows[0]["remedies_list"])

        # Direct remedies
        relations.extend(await _resolve_remedies(db, raw_names))
        # Cross-entity via shared remedies
        relations.extend(await _shared_remedy_entities(db, my_remedies, "therapeutic_index", "condition_name", "condition"))
        relations.extend(await _shared_remedy_entities(db, my_remedies, "organ_preparations", "organ_name", "organ"))
        # Etiology via matching category
        cat = rows[0]["category"]
        mapped_type = _CATEGORY_MAP.get(cat)
        if mapped_type:
            etio_rows = await db.execute_fetchall(
                "SELECT id, agent_name FROM etiology WHERE agent_type = ? LIMIT 10",
                (mapped_type,),
            )
            for e in etio_rows:
                relations.append({"type": "etiology", "id": e["id"], "name": e["agent_name"]})
        # Also via shared remedies (if category match didn't find enough)
        etio_from_remedies = await _shared_remedy_entities(db, my_remedies, "etiology", "agent_name", "etiology")
        existing_etio_ids = {r["id"] for r in relations if r["type"] == "etiology"}
        for e in etio_from_remedies:
            if e["id"] not in existing_etio_ids:
                relations.append(e)

    elif entity_type == "etiology":
        rows = await db.execute_fetchall(
            "SELECT id, agent_name, remedies_list, agent_type, disease_system FROM etiology WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Etiology not found")
        center = {"type": "etiology", "id": rows[0]["id"], "name": rows[0]["agent_name"]}
        raw_names = json.loads(rows[0]["remedies_list"]) if rows[0]["remedies_list"] else []
        my_remedies = _parse_remedies(rows[0]["remedies_list"])

        # Direct remedies
        relations.extend(await _resolve_remedies(db, raw_names))
        # Cross-entity via shared remedies
        relations.extend(await _shared_remedy_entities(db, my_remedies, "therapeutic_index", "condition_name", "condition"))
        relations.extend(await _shared_remedy_entities(db, my_remedies, "organ_preparations", "organ_name", "organ"))
        # Nosodes via matching agent_type
        agent_type = rows[0]["agent_type"]
        mapped_cat = _CATEGORY_MAP.get(agent_type)
        if mapped_cat:
            nos_rows = await db.execute_fetchall(
                "SELECT id, name_lat FROM nosodes WHERE category = ? LIMIT 10",
                (mapped_cat,),
            )
            for n in nos_rows:
                relations.append({"type": "nosode", "id": n["id"], "name": n["name_lat"]})
        # Also via shared remedies
        nos_from_remedies = await _shared_remedy_entities(db, my_remedies, "nosodes", "name_lat", "nosode")
        existing_nos_ids = {r["id"] for r in relations if r["type"] == "nosode"}
        for n in nos_from_remedies:
            if n["id"] not in existing_nos_ids:
                relations.append(n)

    elif entity_type == "organ":
        rows = await db.execute_fetchall(
            "SELECT id, organ_name, remedies_list FROM organ_preparations WHERE id = ?",
            (entity_id,),
        )
        if not rows:
            raise HTTPException(404, "Organ preparation not found")
        center = {"type": "organ", "id": rows[0]["id"], "name": rows[0]["organ_name"]}
        raw_names = json.loads(rows[0]["remedies_list"]) if rows[0]["remedies_list"] else []
        my_remedies = _parse_remedies(rows[0]["remedies_list"])

        # Direct remedies
        relations.extend(await _resolve_remedies(db, raw_names))
        # Cross-entity via shared remedies
        relations.extend(await _shared_remedy_entities(db, my_remedies, "therapeutic_index", "condition_name", "condition"))
        relations.extend(await _shared_remedy_entities(db, my_remedies, "nosodes", "name_lat", "nosode"))
        relations.extend(await _shared_remedy_entities(db, my_remedies, "etiology", "agent_name", "etiology"))

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
