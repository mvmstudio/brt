"use client"

import { useReaderStore } from "@/stores/reader"
import { ChevronLeft, ChevronRight, Pill } from "lucide-react"
import { useState, useRef, useEffect } from "react"
import Link from "next/link"

export function BottomNav() {
  const { currentPage, totalPages, setPage, prevPage, nextPage } = useReaderStore()
  const [inputValue, setInputValue] = useState("")
  const [editing, setEditing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const num = parseInt(inputValue, 10)
    if (num >= 1 && num <= totalPages) {
      setPage(num)
    }
    setEditing(false)
    setInputValue("")
  }

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.select()
    }
  }, [editing])

  const progress = totalPages > 0 ? (currentPage / totalPages) * 100 : 0

  return (
    <footer
      id="bottom-nav"
      className="shrink-0"
      style={{
        background: "var(--bg-secondary)",
        boxShadow: "0 -1px 0 var(--border-subtle)",
      }}
    >
      {/* Progress track */}
      <div className="relative h-[3px] w-full" style={{ background: "var(--border-subtle)" }}>
        <div
          className="absolute left-0 top-0 h-full transition-all duration-500 ease-out"
          style={{
            width: `${progress}%`,
            background: `linear-gradient(90deg, var(--accent-warm), var(--accent-light))`,
            borderRadius: "0 2px 2px 0",
          }}
        />
      </div>

      <div
        className="flex items-center justify-between px-2 py-1.5"
        style={{ fontFamily: "var(--font-sans)" }}
      >
        {/* Handbook link */}
        <Link
          href="/handbook"
          className="flex items-center gap-1 px-2 py-1.5 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          style={{ color: "var(--accent-warm)" }}
        >
          <Pill size={16} strokeWidth={1.25} />
          <span className="text-[11px] font-medium">Справочник</span>
        </Link>

        {/* Prev button */}
        <button
          onClick={prevPage}
          disabled={currentPage <= 1}
          className="p-2.5 rounded-lg transition-all duration-200 hover:scale-110 active:scale-95 disabled:opacity-20 disabled:hover:scale-100"
          aria-label="Предыдущая страница"
        >
          <ChevronLeft size={22} strokeWidth={1.25} />
        </button>

        {/* Page indicator */}
        <div className="flex items-center">
          {editing ? (
            <form onSubmit={handleSubmit} className="flex items-center gap-1.5">
              <input
                ref={inputRef}
                type="number"
                inputMode="numeric"
                min={1}
                max={totalPages}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onBlur={() => {
                  setEditing(false)
                  setInputValue("")
                }}
                className="w-14 text-center rounded-md border px-1 py-1 text-sm tabular-nums"
                style={{
                  borderColor: "var(--accent-warm)",
                  background: "var(--bg-primary)",
                  color: "var(--text-primary)",
                  outline: "none",
                  boxShadow: "0 0 0 2px var(--accent-glow)",
                }}
              />
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                / {totalPages}
              </span>
            </form>
          ) : (
            <button
              onClick={() => {
                setEditing(true)
                setInputValue(String(currentPage))
              }}
              className="flex items-center gap-1 px-3 py-1 rounded-md transition-all duration-200 hover:scale-105 active:scale-95"
              style={{ color: "var(--text-secondary)" }}
            >
              <span className="text-sm font-medium tabular-nums">{currentPage}</span>
              <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                / {totalPages}
              </span>
            </button>
          )}
        </div>

        {/* Next button */}
        <button
          onClick={nextPage}
          disabled={currentPage >= totalPages}
          className="p-2.5 rounded-lg transition-all duration-200 hover:scale-110 active:scale-95 disabled:opacity-20 disabled:hover:scale-100"
          aria-label="Следующая страница"
        >
          <ChevronRight size={22} strokeWidth={1.25} />
        </button>
      </div>
    </footer>
  )
}
