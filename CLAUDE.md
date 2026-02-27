# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## О проекте

Информационный справочник по симптомам, заболеваниям и гомеопатии на основе книги Юсупова Г.А. "Энергоинформационная медицина" (482 стр., сканированный PDF). PWA с мобильным фокусом для практикующих врачей/гомеопатов.

**Repo:** `git@github.com:mvmstudio/brt.git`
**Домен (план):** `https://brt.mvm.st`

---

## Команды разработки

### Backend
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm run dev          # порт 3003 (настроен в package.json)
npm run build        # production build
npm run lint         # ESLint
```

### Оба сервера одновременно
Backend на порту **8000**, frontend на порту **3003**. Запускать в отдельных терминалах.

---

## Стек

### Backend
- **Python 3.14** + FastAPI 0.115.11 + Uvicorn
- **SQLite** (WAL mode, async через aiosqlite)
- **FTS5** — полнотекстовый поиск по книге и справочнику
- **Groq API** (llama-3.3-70b-versatile) через SOCKS5 прокси — для RAG-ассистента (Phase 5)
- **PyMuPDF** — парсинг PDF
- **Pydantic Settings v2** — конфигурация через `.env`

### Frontend
- **Next.js 16.1.6** (App Router) + React 19.2.3 + TypeScript 5
- **Tailwind CSS 4** + PostCSS
- **Zustand 5** — state management (с persist в localStorage)
- **Lucide React** — иконки (strokeWidth: 1.25)
- **DOMPurify** — sanitize HTML из книги
- Шрифты: **Literata** (serif, книга), **Manrope** (sans, UI)

---

## Архитектура

```
Frontend (Next.js, порт 3003)
  ↕ HTTP/CORS
Backend (FastAPI, порт 8000)
  ↕
SQLite (WAL) + images/ (482 PNG)
```

### Два основных модуля

1. **Reader** — постраничная читалка книги (HTML/image), оглавление, закладки, аннотации, поиск FTS5
2. **Handbook** — структурированный справочник (заболевания ↔ препараты ↔ нозоды ↔ этиология ↔ органы), FTS5 по всем разделам

### Ключевые архитектурные решения

- **Singleton DB connection** — `backend/app/db/connection.py` хранит глобальный `_db`, инициализируется через FastAPI lifespan
- **Schema auto-create** — все таблицы создаются в `init_schema()` при первом запуске, миграции не используются
- **Zustand persist** — состояние читалки (currentPage, theme) сохраняется в localStorage под ключом `brt-reader`
- **Страницы двух типов** — `render_mode: "html"` (416 стр., OCR текст) и `"image"` (66 стр., PNG таблиц/формул)
- **API client** — единый `fetchAPI<T>()` в `frontend/src/lib/api.ts`, все типы и вызовы в одном файле
- **Темы** — CSS custom properties через `data-theme` атрибут на `<html>`, 3 варианта (light/sepia/dark)

---

## База данных (SQLite)

Схема в `backend/app/db/connection.py:init_schema()`.

### Reader-таблицы

| Таблица | Назначение |
|---------|-----------|
| `pages` | 482 страницы (html_content, plain_text, render_mode) |
| `pages_fts` | FTS5 по тексту книги |
| `toc` | Оглавление (97 записей, 4 уровня, parent_id) |
| `bookmarks` | Закладки (UNIQUE по page_num) |
| `annotations` | Аннотации с цветом и позицией |
| `reading_progress` | Singleton (id=1), текущая страница |

### Handbook-таблицы

| Таблица | Назначение |
|---------|-----------|
| `remedies` | Materia Medica — гомеопатические препараты (name_lat, name_rus, summary) |
| `remedy_symptoms` | Симптомы препаратов по системам органов |
| `therapeutic_index` | Заболевания → список препаратов (remedies_list хранится как JSON array) |
| `nosodes` | Нозоды (бактерии, вирусы и т.д.) с категориями |
| `etiology` | Этиологические факторы (disease_system → agent_type → agent_name) |
| `organ_preparations` | Органные препараты по категориям заболеваний |
| `handbook_fts` | FTS5 по всем разделам справочника |

**Важно:** `therapeutic_index.remedies_list` — JSON-строка `["Remedy1", "Remedy2"]`, парсится через `json.loads()` в API.

---

## API Endpoints

Все роутеры подключены в `backend/app/main.py` с prefix `/api`.

### Reader
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/toc` | Оглавление |
| GET | `/api/pages/{n}` | Страница (HTML или image mode) |
| GET | `/api/pages/{n}/image` | PNG изображение |
| POST | `/api/search` | FTS5 поиск `{query, limit}` |
| GET/POST/DELETE | `/api/bookmarks[/{n}]` | CRUD закладки |
| GET/POST/DELETE | `/api/annotations[/{id}]` | CRUD аннотации |

### Handbook
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/handbook/stats` | Кол-во записей по всем разделам |
| GET | `/api/handbook/search?q=` | FTS5 поиск по справочнику |
| GET | `/api/handbook/conditions` | Список заболеваний |
| GET | `/api/handbook/conditions/{id}` | Заболевание + enriched remedies |
| GET | `/api/handbook/remedies` | Список препаратов |
| GET | `/api/handbook/remedies/{id}` | Препарат + симптомы + related conditions |
| GET | `/api/handbook/nosodes?category=` | Нозоды с фильтром |
| GET | `/api/handbook/etiology?disease_system=&agent_type=` | Этиология с фильтрами |
| GET | `/api/handbook/organs?category=` | Органные препараты с фильтром |
| GET | `/api/health` | Health check |

---

## Frontend Routes

| Route | Компонент | Назначение |
|-------|-----------|-----------|
| `/` | `app/page.tsx` | Читалка книги (TopBar, PageView, BottomNav, TocSidebar) |
| `/search` | `app/search/page.tsx` | Полнотекстовый поиск |
| `/handbook` | `app/handbook/page.tsx` | Справочник (6 табов: Поиск, Заболевания, Препараты, Нозоды, Этиология, Органы) |
| `/chat` | `app/chat/page.tsx` | Заглушка для RAG-ассистента |

---

## Дизайн-система

### Темы (CSS custom properties в `globals.css`)

| Тема | Фон | Текст | Акцент |
|------|-----|-------|--------|
| light | #f8f6f1 | #2c2825 | #b8860b (gold) |
| sepia | #f2ead5 | #3a2e1e | #a0651a (brown) |
| dark | #0e0e1a | #e8e5df | #d4a520 (gold) |

### Иконки
Lucide React, strokeWidth: 1.25

### Шрифты
- Книга: Literata (serif, `--font-serif`)
- UI: Manrope (sans-serif, `--font-sans`)

---

## Переменные окружения

**backend/.env** (все поля — см. `backend/app/config.py`):
```
DATABASE_PATH=data/brt.db
PDF_PATH=../Энергоинформационная медицина(скан).pdf
DATA_DIR=data
CORS_ORIGINS=http://localhost:3003,https://brt.mvm.st
GROQ_API_KEY=...
GROQ_PROXY_URL=socks5h://...
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=...
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=brt_book
```

**Важно:** `config.py` содержит дефолты для всех полей, `.env` переопределяет. Groq клиент использует `openai` SDK (OpenAI-compatible API) через SOCKS5 прокси (`backend/app/services/groq_client.py`).

**frontend/.env.local:**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Текущий статус

### Реализовано
- [x] Парсинг PDF → SQLite + PNG
- [x] Читалка (постраничная навигация, HTML/image)
- [x] Оглавление (иерархия, sidebar)
- [x] Полнотекстовый поиск (FTS5)
- [x] Закладки + аннотации
- [x] 3 темы оформления
- [x] Swipe-навигация, клавиатура
- [x] Справочник — Handbook (заболевания, препараты, нозоды, этиология, органы)
- [x] FTS5 поиск по справочнику
- [x] Cross-referencing: заболевания ↔ препараты

### Не реализовано
- [ ] RAG Chat-ассистент (Phase 5)
- [ ] Qdrant + embeddings
- [ ] PWA (Service Worker, manifest.json)
- [ ] Офлайн-режим
- [ ] Деплой (nginx, CI/CD)

### Известные проблемы
- `frontend/src/lib/api.ts:1` — fallback порт 8002, а backend на 8000. Без `.env.local` frontend не соединится.
- `manifest.json` не существует в `frontend/public/`
- `deploy/` и `nginx/` — пустые директории
- **Кросс-ссылки сломаны на ~87%** — `therapeutic_index.remedies_list` хранит имена ("Calcarea carbonica"), а `remedies.name_lat` — другие формы ("ACONITUM"). Только ~20 из ~534 уникальных имён резолвятся → Issue #2
- **Нет описаний** у `therapeutic_index`, `nosodes`, `etiology`, `organ_preparations` → Issue #2

---

## Правила разработки

- Язык интерфейса: **русский**
- Иконки: Lucide React (strokeWidth: 1.25), **эмодзи в UI ЗАПРЕЩЕНЫ**
- TypeScript strict mode, Python type hints + async/await
- API path prefix: `/api/`
- Импорты frontend: `@/*` → `./src/*`
- Стили: Tailwind CSS 4 utility classes + CSS custom properties
- State: Zustand с persist middleware
- HTML из книги: sanitize через DOMPurify
- Данные из PDF не хранятся в git (gitignore: `*.pdf`, `*.db`, `images/`)
