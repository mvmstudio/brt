"use client"

import { useReaderStore } from "@/stores/reader"
import { X, BookOpen } from "lucide-react"
import { useEffect, useRef } from "react"

export function TocSidebar() {
  const { toc, tocOpen, setTocOpen, setPage, currentPage } = useReaderStore()
  const sidebarRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLButtonElement>(null)

  // Escape to close
  useEffect(() => {
    if (!tocOpen) return
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setTocOpen(false)
    }
    window.addEventListener("keydown", handleEsc)
    return () => window.removeEventListener("keydown", handleEsc)
  }, [tocOpen, setTocOpen])

  // Scroll active entry into view
  useEffect(() => {
    if (tocOpen && activeRef.current) {
      activeRef.current.scrollIntoView({ block: "center", behavior: "smooth" })
    }
  }, [tocOpen])

  // Prevent body scroll when sidebar open
  useEffect(() => {
    if (tocOpen) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => { document.body.style.overflow = "" }
  }, [tocOpen])

  if (!tocOpen) return null

  const handleClick = (pageNum: number) => {
    setPage(pageNum)
    setTocOpen(false)
  }

  // Find which TOC entry is "current" based on page
  const findActiveEntry = () => {
    for (let i = toc.length - 1; i >= 0; i--) {
      if (currentPage >= toc[i].page_num) return toc[i].id
    }
    return toc[0]?.id
  }
  const activeId = findActiveEntry()

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 animate-fade-in"
        style={{ background: "var(--overlay)" }}
        onClick={() => setTocOpen(false)}
      />

      {/* Sidebar */}
      <aside
        ref={sidebarRef}
        id="toc-sidebar"
        className="fixed top-0 left-0 z-50 h-full w-[320px] max-w-[85vw] overflow-y-auto animate-slide-in"
        style={{
          background: "var(--bg-secondary)",
          boxShadow: "var(--shadow-lg)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 sticky top-0 z-10 glass"
          style={{
            background: "var(--bg-secondary)",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div className="flex items-center gap-2.5">
            <BookOpen size={18} strokeWidth={1.25} style={{ color: "var(--accent-warm)" }} />
            <h2
              className="text-sm font-semibold tracking-wide uppercase"
              style={{
                fontFamily: "var(--font-sans)",
                letterSpacing: "0.06em",
                color: "var(--text-primary)",
              }}
            >
              Оглавление
            </h2>
          </div>
          <button
            onClick={() => setTocOpen(false)}
            className="p-1.5 rounded-lg transition-all duration-200 hover:scale-110 active:scale-95"
            style={{ color: "var(--text-muted)" }}
            aria-label="Закрыть оглавление"
          >
            <X size={18} strokeWidth={1.25} />
          </button>
        </div>

        {/* TOC entries */}
        <nav className="py-2 pb-8">
          {toc.map((entry, i) => {
            const isActive = entry.id === activeId
            const isSection = entry.level === 0

            return (
              <button
                key={entry.id}
                ref={isActive ? activeRef : undefined}
                onClick={() => handleClick(entry.page_num)}
                className="w-full text-left flex items-baseline gap-2 transition-all duration-150"
                style={{
                  padding: `${isSection ? 10 : 7}px 20px`,
                  paddingLeft: `${entry.level * 14 + 20}px`,
                  fontFamily: isSection ? "var(--font-sans)" : "inherit",
                  fontSize: isSection ? "0.82rem" : entry.level <= 1 ? "0.85rem" : "0.8rem",
                  fontWeight: isSection ? 700 : entry.level <= 1 ? 500 : 400,
                  color: isActive ? "var(--accent-warm)" : isSection ? "var(--text-primary)" : "var(--text-secondary)",
                  letterSpacing: isSection ? "0.03em" : undefined,
                  textTransform: isSection ? "uppercase" : undefined,
                  background: isActive ? "var(--accent-glow)" : "transparent",
                  borderLeft: isActive ? "2px solid var(--accent-warm)" : "2px solid transparent",
                  marginTop: isSection && i > 0 ? "12px" : undefined,
                  lineHeight: "1.4",
                }}
              >
                <span className="flex-1">{entry.title}</span>
                <span
                  className="text-[11px] shrink-0 tabular-nums font-normal"
                  style={{
                    fontFamily: "var(--font-sans)",
                    color: isActive ? "var(--accent-warm)" : "var(--text-muted)",
                    opacity: isActive ? 1 : 0.6,
                  }}
                >
                  {entry.page_num}
                </span>
              </button>
            )
          })}

          {toc.length === 0 && (
            <div className="px-5 py-12 text-center">
              <div className="skeleton h-4 w-3/4 mx-auto mb-3" />
              <div className="skeleton h-4 w-1/2 mx-auto mb-3" />
              <div className="skeleton h-4 w-2/3 mx-auto" />
            </div>
          )}
        </nav>
      </aside>
    </>
  )
}
