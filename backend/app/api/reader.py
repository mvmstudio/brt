from fastapi import APIRouter, HTTPException

from app.db.connection import get_db

router = APIRouter()


@router.get("/toc")
async def get_toc():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, level, title, page_num, parent_id, sort_order FROM toc ORDER BY sort_order"
    )
    return [dict(r) for r in rows]


@router.get("/pages/{page_num}")
async def get_page(page_num: int):
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM pages WHERE page_num = ?", (page_num,)
    )
    if not row:
        raise HTTPException(404, f"Page {page_num} not found")
    page = dict(row[0])

    total = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM pages")
    page["total_pages"] = total[0]["cnt"]
    return page


@router.get("/pages/{page_num}/image")
async def get_page_image(page_num: int):
    from fastapi.responses import FileResponse
    from pathlib import Path
    from app.config import settings

    img_path = Path(settings.data_dir) / "images" / f"page_{page_num:04d}.png"
    if not img_path.exists():
        raise HTTPException(404, f"Image for page {page_num} not found")
    return FileResponse(str(img_path), media_type="image/png")
