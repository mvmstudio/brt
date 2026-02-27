"use client"

import { useReaderStore } from "@/stores/reader"
import { api } from "@/lib/api"
import { Image as ImageIcon, AlertTriangle, RotateCcw } from "lucide-react"
import { useState, useEffect, useCallback, useRef } from "react"
import DOMPurify from "dompurify"

/* ─── Safe HTML renderer with DOMPurify ─── */
function SafeHtml({ html }: { html: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (ref.current) {
      const clean = DOMPurify.sanitize(html, {
        ALLOWED_TAGS: [
          "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr",
          "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
          "strong", "em", "b", "i", "u", "mark", "sub", "sup",
          "div", "span", "img", "a", "blockquote", "pre", "code",
        ],
        ALLOWED_ATTR: ["class", "src", "alt", "href", "loading", "colspan", "rowspan"],
      })
      ref.current.innerHTML = clean
    }
  }, [html])

  return <div ref={ref} className="page-content animate-fade-in" />
}

/* ─── Loading Skeleton ─── */
function LoadingSkeleton() {
  return (
    <div className="max-w-[680px] mx-auto px-4 py-8 space-y-4 animate-fade-in">
      <div className="skeleton h-7 w-3/4" />
      <div className="skeleton h-4 w-full" />
      <div className="skeleton h-4 w-full" />
      <div className="skeleton h-4 w-5/6" />
      <div className="skeleton h-4 w-full" style={{ animationDelay: "0.1s" }} />
      <div className="skeleton h-4 w-4/5" style={{ animationDelay: "0.1s" }} />
      <div className="h-4" />
      <div className="skeleton h-4 w-full" style={{ animationDelay: "0.2s" }} />
      <div className="skeleton h-4 w-full" style={{ animationDelay: "0.2s" }} />
      <div className="skeleton h-4 w-3/5" style={{ animationDelay: "0.2s" }} />
      <div className="h-4" />
      <div className="skeleton h-4 w-full" style={{ animationDelay: "0.3s" }} />
      <div className="skeleton h-4 w-full" style={{ animationDelay: "0.3s" }} />
      <div className="skeleton h-4 w-2/3" style={{ animationDelay: "0.3s" }} />
    </div>
  )
}

/* ─── Error State ─── */
function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-8 animate-fade-in">
      <div
        className="p-4 rounded-full"
        style={{ background: "var(--accent-glow)" }}
      >
        <AlertTriangle size={28} strokeWidth={1.25} style={{ color: "var(--accent-warm)" }} />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium mb-1" style={{ fontFamily: "var(--font-sans)" }}>
          Не удалось загрузить страницу
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Проверьте соединение и попробуйте снова
        </p>
      </div>
      <button
        onClick={onRetry}
        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all duration-200 hover:scale-105 active:scale-95"
        style={{
          fontFamily: "var(--font-sans)",
          background: "var(--accent)",
          color: "white",
        }}
      >
        <RotateCcw size={14} strokeWidth={1.25} />
        Повторить загрузку
      </button>
    </div>
  )
}

/* ─── Main PageView ─── */
export function PageView() {
  const { pageData, loading, currentPage, totalPages, nextPage, prevPage, setPage } = useReaderStore()
  const [showOriginal, setShowOriginal] = useState(false)
  const [touchStart, setTouchStart] = useState<number | null>(null)
  const [error, setError] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  // Scroll to top on page change
  useEffect(() => {
    contentRef.current?.scrollTo(0, 0)
    setShowOriginal(false)
    setError(false)
  }, [currentPage])

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault()
        nextPage()
      } else if (e.key === "ArrowLeft") {
        e.preventDefault()
        prevPage()
      }
    },
    [nextPage, prevPage]
  )

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handleKeyDown])

  // Swipe navigation
  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStart(e.touches[0].clientX)
  }

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStart === null) return
    const diff = e.changedTouches[0].clientX - touchStart
    if (Math.abs(diff) > 80) {
      if (diff > 0) prevPage()
      else nextPage()
    }
    setTouchStart(null)
  }

  // Error state
  if (error) {
    return <ErrorState onRetry={() => setPage(currentPage)} />
  }

  // Loading state
  if (loading || !pageData) {
    return <LoadingSkeleton />
  }

  const imageUrl = api.getPageImageUrl(currentPage)

  return (
    <div
      ref={contentRef}
      id="page-view"
      className="px-4 py-6 sm:px-6 md:px-8 lg:px-12"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Toggle: HTML ↔ Original image */}
      <div className="max-w-[680px] mx-auto flex justify-end mb-3">
        <button
          onClick={() => setShowOriginal(!showOriginal)}
          className="flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-md transition-all duration-200 hover:scale-105 active:scale-95"
          style={{
            fontFamily: "var(--font-sans)",
            background: showOriginal ? "var(--accent-glow)" : "transparent",
            color: showOriginal ? "var(--accent-warm)" : "var(--text-muted)",
            border: `1px solid ${showOriginal ? "var(--accent-warm)" : "var(--border)"}`,
          }}
        >
          <ImageIcon size={12} strokeWidth={1.25} />
          {showOriginal ? "Текст" : "Оригинал PDF"}
        </button>
      </div>

      {/* Content */}
      {showOriginal || pageData.render_mode === "image" ? (
        <div className="page-image-container animate-fade-in">
          <img
            src={imageUrl}
            alt={`Страница ${currentPage}`}
            loading="lazy"
          />
        </div>
      ) : (
        <SafeHtml html={pageData.html_content} />
      )}

      {/* Page number footer */}
      <div
        className="max-w-[680px] mx-auto mt-8 pt-4 text-center"
        style={{
          borderTop: "1px solid var(--border-subtle)",
          fontFamily: "var(--font-sans)",
        }}
      >
        <span className="text-[11px] tabular-nums tracking-wide" style={{ color: "var(--text-muted)" }}>
          — {currentPage} —
        </span>
      </div>
    </div>
  )
}
