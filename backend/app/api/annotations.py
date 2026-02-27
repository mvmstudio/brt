from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.connection import get_db

router = APIRouter()


class AnnotationCreate(BaseModel):
    page_num: int
    text_fragment: str | None = None
    comment: str
    position_start: int | None = None
    position_end: int | None = None
    color: str = "#fef08a"


@router.get("/annotations")
async def list_annotations(page_num: int | None = None):
    db = await get_db()
    if page_num is not None:
        rows = await db.execute_fetchall(
            "SELECT * FROM annotations WHERE page_num = ? ORDER BY created_at DESC",
            (page_num,),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT * FROM annotations ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


@router.post("/annotations")
async def create_annotation(ann: AnnotationCreate):
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO annotations (page_num, text_fragment, comment, position_start, position_end, color)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (ann.page_num, ann.text_fragment, ann.comment, ann.position_start, ann.position_end, ann.color),
    )
    await db.commit()
    return {"status": "created", "id": cursor.lastrowid}


@router.delete("/annotations/{ann_id}")
async def delete_annotation(ann_id: int):
    db = await get_db()
    cursor = await db.execute("DELETE FROM annotations WHERE id = ?", (ann_id,))
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(404, "Annotation not found")
    return {"status": "deleted"}
