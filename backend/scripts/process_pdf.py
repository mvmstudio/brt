"""
PDF → HTML + PNG processing pipeline.
Converts 482 pages of the book into:
- HTML content (for text and simple tables)
- PNG images (for complex tables with >5 columns)
- Plain text (for FTS5 search index)
Stores everything in SQLite.
"""
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymupdf
import pymupdf4llm
import aiosqlite
import asyncio
import markdown
from pathlib import Path

from app.config import settings

PDF_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", settings.pdf_path)
)
DATA_DIR = Path(os.path.dirname(__file__)).parent / settings.data_dir
IMAGES_DIR = DATA_DIR / "images"
HTML_DIR = DATA_DIR / "html"
DB_PATH = DATA_DIR / "brt.db"

SHORT_LINE_THRESHOLD = 0.80  # Pages with >80% short lines are tables → render as image
SHORT_LINE_MAX_LEN = 30


def analyze_page(doc: pymupdf.Document, page_idx: int) -> dict:
    """Analyze a single page to determine render mode and extract metadata.

    For scanned PDFs, pymupdf table detection doesn't work. Instead we use
    a heuristic: pages where >80% of lines are short (<30 chars) are likely
    tables and should render as original scan images.
    """
    page = doc[page_idx]
    has_images = bool(page.get_images())
    text = page.get_text().strip()
    lines = [l for l in text.split('\n') if l.strip()]
    total_lines = len(lines)

    if total_lines == 0:
        # Empty page
        return {
            "page_num": page_idx + 1,
            "has_tables": False,
            "has_images": has_images,
            "render_mode": "image",
        }

    short_lines = sum(1 for l in lines if len(l.strip()) < SHORT_LINE_MAX_LEN)
    short_ratio = short_lines / total_lines

    has_tables = short_ratio > SHORT_LINE_THRESHOLD
    render_mode = "image" if has_tables else "html"

    return {
        "page_num": page_idx + 1,
        "has_tables": has_tables,
        "has_images": has_images,
        "render_mode": render_mode,
    }


def render_page_image(doc: pymupdf.Document, page_idx: int, output_path: Path) -> None:
    """Render a page as PNG image at 2x resolution."""
    page = doc[page_idx]
    mat = pymupdf.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    pix.save(str(output_path))


def dehyphenate(text: str) -> str:
    """Remove soft hyphens (U+00AD) and regular hyphens at line breaks, joining split words.

    Handles patterns:
    - word\u00ad\\n\\nrest  → wordrest (soft hyphen + paragraph break)
    - word\u00ad\\nrest   → wordrest (soft hyphen + line break)
    - word-\\n\\nrest    → wordrest (regular hyphen + paragraph break, only for lowercase continuation)
    - word-\\nrest      → wordrest (regular hyphen + line break, only for lowercase continuation)
    """
    # Soft hyphen + any newlines → join
    text = re.sub(r'\xad\s*\n+\s*', '', text)
    # Regular hyphen at end of line, followed by lowercase continuation → join
    # (careful: don't remove real hyphens like "электро-магнитный")
    text = re.sub(r'(\w)-\s*\n+\s*([а-яёa-z])', r'\1\2', text)
    return text


def split_into_paragraphs(text: str) -> list[str]:
    """Split OCR text into paragraphs using heuristics.

    Scanned PDFs produce raw line-by-line text without paragraph markers.
    We detect paragraph boundaries by:
    - Short lines (<60% of typical width) followed by uppercase start → paragraph break
    - Lines ending with period/colon and next starts with uppercase → paragraph break
    """
    lines = text.split('\n')
    if not lines:
        return []

    # Calculate typical line width (median of non-empty lines)
    lengths = sorted(len(l) for l in lines if len(l.strip()) > 10)
    typical_width = lengths[len(lengths) // 2] if lengths else 70
    short_threshold = typical_width * 0.6

    paragraphs = []
    current = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(' '.join(current))
                current = []
            continue

        current.append(stripped)

        # Check if this line ends a paragraph
        is_short = len(stripped) < short_threshold
        ends_sentence = stripped[-1] in '.!?:»"'
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        next_starts_upper = bool(next_line) and (next_line[0].isupper() or next_line[0].isdigit())

        if is_short and ends_sentence and next_starts_upper:
            paragraphs.append(' '.join(current))
            current = []

    if current:
        paragraphs.append(' '.join(current))

    return paragraphs


def convert_page_to_html(doc: pymupdf.Document, page_idx: int) -> tuple[str, str]:
    """Convert a single page to HTML and plain text.

    For scanned PDFs, pymupdf4llm returns empty results (it only sees images).
    We use page.get_text() which extracts the OCR text layer, then split into
    paragraphs with dehyphenation.
    """
    page = doc[page_idx]
    raw_text = page.get_text().strip()

    if not raw_text:
        return "", ""

    # Fix hyphenation
    raw_text = dehyphenate(raw_text)

    # Plain text for FTS search
    plain_text = re.sub(r'\n{3,}', '\n\n', raw_text).strip()
    plain_text = dehyphenate(plain_text)

    # Split into paragraphs and convert to HTML
    paragraphs = split_into_paragraphs(raw_text)
    html_parts = []
    for p in paragraphs:
        p = re.sub(r' {2,}', ' ', p).strip()
        if not p:
            continue
        html_parts.append(f"<p>{p}</p>")

    html_content = "\n".join(html_parts)
    return html_content, plain_text


async def process_all():
    """Main processing pipeline."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Opening PDF: {PDF_PATH}", flush=True)
    doc = pymupdf.open(PDF_PATH)
    total = len(doc)
    print(f"Total pages: {total}", flush=True)

    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute("PRAGMA journal_mode=WAL")

    # Create tables
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
            plain_text, title, content=pages, content_rowid=page_num, tokenize='unicode61'
        );
    """)

    # Clear existing data
    await db.execute("DELETE FROM pages")
    await db.execute("DELETE FROM pages_fts")
    await db.commit()

    image_count = 0
    html_count = 0
    errors = []

    for page_idx in range(total):
        page_num = page_idx + 1
        try:
            info = analyze_page(doc, page_idx)
            render_mode = info["render_mode"]

            # Always render PNG
            img_path = IMAGES_DIR / f"page_{page_num:04d}.png"
            render_page_image(doc, page_idx, img_path)

            # Convert to HTML/text
            html_content = ""
            plain_text = ""
            if render_mode == "html":
                html_content, plain_text = convert_page_to_html(doc, page_idx)
                html_count += 1
            else:
                # For image-mode pages, extract plain text for search
                page = doc[page_idx]
                plain_text = page.get_text().strip()
                html_content = f'<div class="page-image-container"><img src="/static/images/page_{page_num:04d}.png" alt="Страница {page_num}" loading="lazy" /></div>'
                image_count += 1

            await db.execute(
                """INSERT OR REPLACE INTO pages
                (page_num, render_mode, html_content, plain_text, has_tables, has_images)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (page_num, render_mode, html_content, plain_text,
                 int(info["has_tables"]), int(info["has_images"])),
            )

            # FTS5 index
            await db.execute(
                "INSERT INTO pages_fts(rowid, plain_text, title) VALUES (?, ?, ?)",
                (page_num, plain_text, ""),
            )

            if page_num % 20 == 0:
                await db.commit()
                print(f"  Processed {page_num}/{total} pages...", flush=True)

        except Exception as e:
            errors.append((page_num, str(e)))
            print(f"  ERROR page {page_num}: {e}", flush=True)

    await db.commit()
    await db.close()
    doc.close()

    print(f"\nDone! HTML: {html_count}, Image: {image_count}, Errors: {len(errors)}", flush=True)
    if errors:
        print("Errors:")
        for pn, err in errors:
            print(f"  Page {pn}: {err}")


if __name__ == "__main__":
    asyncio.run(process_all())
