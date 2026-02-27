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
    return {"favorites": [dict(r) for r in rows]}


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
