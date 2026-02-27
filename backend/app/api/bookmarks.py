from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.connection import get_db

router = APIRouter()


class BookmarkCreate(BaseModel):
    page_num: int
    title: str | None = None


@router.get("/bookmarks")
async def list_bookmarks():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM bookmarks ORDER BY created_at DESC"
    )
    return [dict(r) for r in rows]


@router.post("/bookmarks")
async def create_bookmark(bm: BookmarkCreate):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO bookmarks (page_num, title) VALUES (?, ?)",
        (bm.page_num, bm.title),
    )
    await db.commit()
    return {"status": "created", "page_num": bm.page_num}


@router.delete("/bookmarks/{page_num}")
async def delete_bookmark(page_num: int):
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM bookmarks WHERE page_num = ?", (page_num,)
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(404, "Bookmark not found")
    return {"status": "deleted"}
