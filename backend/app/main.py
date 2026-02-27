from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.db.connection import get_db, close_db
from app.api import reader, search, chat, bookmarks, annotations, handbook, auth, favorites


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_db()
    yield
    await close_db()


app = FastAPI(
    title="BRT Book Reader",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for page images
images_dir = Path(settings.data_dir) / "images"
images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=str(images_dir)), name="images")

app.include_router(reader.router, prefix="/api", tags=["reader"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(bookmarks.router, prefix="/api", tags=["bookmarks"])
app.include_router(annotations.router, prefix="/api", tags=["annotations"])
app.include_router(handbook.router, prefix="/api", tags=["handbook"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(favorites.router, prefix="/api", tags=["favorites"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
