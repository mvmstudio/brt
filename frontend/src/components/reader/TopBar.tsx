"use client"

import { useReaderStore } from "@/stores/reader"
import {
  Bookmark,
  Search,
  Sun,
  Moon,
  Sunset,
  BookMarked,
  MessageCircle,
  List,
  Pill,
} from "lucide-react"
import Link from "next/link"

export function TopBar() {
  const {
    currentPage,
    pageData,
    bookmarks,
    toggleBookmark,
    theme,
    setTheme,
    setTocOpen,
  } = useReaderStore()

  const isBookmarked = bookmarks.has(currentPage)

  const cycleTheme = () => {
    const themes: ("light" | "dark" | "sepia")[] = ["light", "sepia", "dark"]
    const idx = themes.indexOf(theme)
    setTheme(themes[(idx + 1) % themes.length])
  }

  const themeIcon = {
    light: <Sun size={18} strokeWidth={1.25} />,
    sepia: <Sunset size={18} strokeWidth={1.25} />,
    dark: <Moon size={18} strokeWidth={1.25} />,
  }

  return (
    <header
      id="topbar"
      className="flex items-center justify-between px-3 py-2.5 shrink-0 glass"
      style={{
        background: "var(--bg-secondary)",
        borderBottom: "1px solid var(--border-subtle)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Left: TOC + chapter title */}
      <div className="flex items-center gap-1.5 min-w-0 flex-1">
        <button
          onClick={() => setTocOpen(true)}
          className="shrink-0 p-2 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          style={{ color: "var(--accent-warm)" }}
          aria-label="Оглавление"
        >
          <List size={20} strokeWidth={1.25} />
        </button>

        <div className="min-w-0 flex-1">
          <p
            className="text-[11px] font-medium uppercase tracking-[0.08em] truncate"
            style={{
              fontFamily: "var(--font-sans)",
              color: "var(--text-muted)",
            }}
          >
            Юсупов Г.А.
          </p>
          <p
            className="text-[13px] truncate leading-tight"
            style={{ color: "var(--text-secondary)" }}
          >
            {pageData?.chapter || "Энергоинформационная медицина"}
          </p>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-0.5 shrink-0">
        <Link
          href="/handbook"
          className="p-2 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          aria-label="Справочник"
          style={{ color: "var(--text-muted)" }}
          title="Справочник: заболевания, препараты, нозоды"
        >
          <Pill size={18} strokeWidth={1.25} />
        </Link>

        <button
          onClick={() => toggleBookmark(currentPage, pageData?.chapter || undefined)}
          className="p-2 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          aria-label={isBookmarked ? "Убрать закладку" : "Добавить закладку"}
          style={{ color: isBookmarked ? "var(--accent-warm)" : "var(--text-muted)" }}
        >
          {isBookmarked ? (
            <BookMarked size={18} strokeWidth={1.25} />
          ) : (
            <Bookmark size={18} strokeWidth={1.25} />
          )}
        </button>

        <Link
          href="/search"
          className="p-2 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          style={{ color: "var(--text-muted)" }}
          aria-label="Поиск"
        >
          <Search size={18} strokeWidth={1.25} />
        </Link>

        <Link
          href="/chat"
          className="p-2 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          style={{ color: "var(--text-muted)" }}
          aria-label="AI-ассистент"
        >
          <MessageCircle size={18} strokeWidth={1.25} />
        </Link>

        <button
          onClick={cycleTheme}
          className="p-2 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          aria-label="Сменить тему"
          style={{ color: "var(--text-muted)" }}
        >
          {themeIcon[theme]}
        </button>
      </div>
    </header>
  )
}
