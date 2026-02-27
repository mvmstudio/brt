from fastapi import APIRouter
from pydantic import BaseModel

from app.db.connection import get_db

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 20


@router.post("/search")
async def search(req: SearchRequest):
    db = await get_db()
    rows = await db.execute_fetchall(
        """
        SELECT p.page_num, p.title, p.chapter,
               snippet(pages_fts, 0, '<mark>', '</mark>', '...', 40) as snippet
        FROM pages_fts
        JOIN pages p ON p.page_num = pages_fts.rowid
        WHERE pages_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (req.query, req.limit),
    )
    return {"results": [dict(r) for r in rows], "total": len(rows)}
