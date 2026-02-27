import aiosqlite
from pathlib import Path

from app.config import settings

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(str(db_path))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await init_schema(_db)
    return _db


async def init_schema(db: aiosqlite.Connection) -> None:
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            page_num INTEGER PRIMARY KEY,
            title TEXT,
            chapter TEXT,
            render_mode TEXT NOT NULL DEFAULT 'html',
            html_content TEXT,
            plain_text TEXT,
            has_tables INTEGER DEFAULT 0,
            has_images INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS toc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level INTEGER NOT NULL,
            title TEXT NOT NULL,
            page_num INTEGER NOT NULL,
            parent_id INTEGER REFERENCES toc(id),
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_num INTEGER NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(page_num)
        );

        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_num INTEGER NOT NULL,
            text_fragment TEXT,
            comment TEXT NOT NULL,
            position_start INTEGER,
            position_end INTEGER,
            color TEXT DEFAULT '#fef08a',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reading_progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_page INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        INSERT OR IGNORE INTO reading_progress (id, current_page) VALUES (1, 1);

        CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            plain_text,
            title,
            content=pages,
            content_rowid=page_num,
            tokenize='unicode61'
        );

        -- Справочник: Препараты Материа Медика
        CREATE TABLE IF NOT EXISTS remedies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_lat TEXT NOT NULL UNIQUE,
            name_rus TEXT,
            source_pages TEXT,
            summary TEXT,
            content_source TEXT DEFAULT 'book'
        );

        -- Справочник: Симптомы по системам органов
        CREATE TABLE IF NOT EXISTS remedy_symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remedy_id INTEGER NOT NULL REFERENCES remedies(id) ON DELETE CASCADE,
            system TEXT NOT NULL,
            system_name TEXT NOT NULL,
            description TEXT NOT NULL
        );

        -- Справочник: Терапевтический указатель
        CREATE TABLE IF NOT EXISTS therapeutic_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_name TEXT NOT NULL,
            remedies_list TEXT NOT NULL,
            source_page INTEGER,
            description TEXT,
            content_source TEXT DEFAULT 'book'
        );

        -- Справочник: Нозоды
        CREATE TABLE IF NOT EXISTS nosodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER,
            name_lat TEXT NOT NULL,
            name_rus TEXT,
            category TEXT,
            source_page INTEGER,
            description TEXT,
            remedies_list TEXT,
            content_source TEXT DEFAULT 'book'
        );

        -- Справочник: Этиологические факторы
        CREATE TABLE IF NOT EXISTS etiology (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_system TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            agent_name_rus TEXT,
            source_page INTEGER,
            description TEXT,
            remedies_list TEXT,
            content_source TEXT DEFAULT 'book'
        );

        -- Справочник: Органные препараты
        CREATE TABLE IF NOT EXISTS organ_preparations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_category TEXT,
            organ_name TEXT NOT NULL,
            organ_name_lat TEXT,
            manufacturer TEXT,
            source_page INTEGER,
            description TEXT,
            remedies_list TEXT,
            content_source TEXT DEFAULT 'book'
        );

        -- Справочник: Алиасы препаратов (нормализация имён)
        CREATE TABLE IF NOT EXISTS remedy_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL,
            canonical_remedy_id INTEGER REFERENCES remedies(id),
            source TEXT DEFAULT 'book',
            UNIQUE(alias)
        );

        -- Пользователи (для избранного)
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Избранное
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, entity_type, entity_id)
        );

        -- Справочник: FTS по всем разделам
        CREATE VIRTUAL TABLE IF NOT EXISTS handbook_fts USING fts5(
            type,
            name,
            content,
            entity_id UNINDEXED,
            tokenize='unicode61'
        );
    """)
    await db.commit()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
