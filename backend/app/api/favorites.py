"""
Favorites API — add/remove/list favorite handbook entities.
Requires JWT authentication.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.db.connection import get_db
from app.api.auth import require_user

router = APIRouter()

VALID_ENTITY_TYPES = {"condition", "remedy", "nosode", "etiology", "organ"}


class FavoriteRequest(BaseModel):
    entity_type: str = Field(..., description="condition|remedy|nosode|etiology|organ")
    entity_id: int


@router.get("/favorites")
async def list_favorites(
    entity_type: str | None = None,
    enriched: bool = False,
    user: dict = Depends(require_user),
):
    db = await get_db()
    if entity_type:
        rows = await db.execute_fetchall(
            "SELECT id, entity_type, entity_id, created_at FROM favorites "
            "WHERE user_id = ? AND entity_type = ? ORDER BY created_at DESC",
            (user["id"], entity_type),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT id, entity_type, entity_id, created_at FROM favorites "
            "WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        )

    favorites = [dict(r) for r in rows]

    if enriched and favorites:
        favorites = await _enrich_favorites(db, favorites)

    return {"favorites": favorites}


# Table → (table_name, name_column, secondary_name_column)
_ENTITY_TABLE_MAP = {
    "condition": ("therapeutic_index", "condition_name", None),
    "remedy": ("remedies", "name_lat", "name_rus"),
    "nosode": ("nosodes", "name_lat", "name_rus"),
    "etiology": ("etiology", "agent_name", "agent_name_rus"),
    "organ": ("organ_preparations", "organ_name", "organ_name_lat"),
}


async def _enrich_favorites(db, favorites: list[dict]) -> list[dict]:
    """Add entity_name to each favorite by looking up the source table."""
    grouped: dict[str, list[int]] = {}
    for f in favorites:
        grouped.setdefault(f["entity_type"], []).append(f["entity_id"])

    name_cache: dict[str, dict[int, str]] = {}

    for etype, ids in grouped.items():
        mapping = _ENTITY_TABLE_MAP.get(etype)
        if not mapping:
            continue
        table, name_col, alt_col = mapping
        placeholders = ",".join("?" * len(ids))
        cols = f"id, {name_col}" + (f", {alt_col}" if alt_col else "")
        rows = await db.execute_fetchall(
            f"SELECT {cols} FROM {table} WHERE id IN ({placeholders})", ids
        )
        cache = {}
        for r in rows:
            r = dict(r)
            name = r[name_col] or ""
            if alt_col and r.get(alt_col):
                name = f"{name} ({r[alt_col]})"
            cache[r["id"]] = name
        name_cache[etype] = cache

    for f in favorites:
        cache = name_cache.get(f["entity_type"], {})
        f["entity_name"] = cache.get(f["entity_id"], "")

    return favorites


@router.post("/favorites")
async def add_favorite(body: FavoriteRequest, user: dict = Depends(require_user)):
    if body.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(400, f"Invalid entity_type. Must be one of: {VALID_ENTITY_TYPES}")

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO favorites (user_id, entity_type, entity_id) VALUES (?, ?, ?)",
            (user["id"], body.entity_type, body.entity_id),
        )
        await db.commit()
    except Exception:
        raise HTTPException(409, "Already in favorites")

    return {"status": "added"}


@router.delete("/favorites")
async def remove_favorite(body: FavoriteRequest, user: dict = Depends(require_user)):
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM favorites WHERE user_id = ? AND entity_type = ? AND entity_id = ?",
        (user["id"], body.entity_type, body.entity_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(404, "Not in favorites")
    return {"status": "removed"}
