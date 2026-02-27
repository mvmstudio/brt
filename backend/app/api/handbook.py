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
