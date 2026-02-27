"use client"

import { useState, useEffect, useMemo, useCallback } from "react"
import { ArrowLeft, AlertCircle, SearchX, RefreshCw } from "lucide-react"
import { api, type Remedy, type RemedyDetail } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"
import { FavoriteButton } from "./FavoriteButton"

interface RemediesTabProps {
  initialExpandedId?: number | null
  onAuthRequired?: () => void
  showFavoritesOnly?: boolean
}

export function RemediesTab({ initialExpandedId, onAuthRequired, showFavoritesOnly }: RemediesTabProps) {
  const [remedies, setRemedies] = useState<Remedy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState("")
  const [detail, setDetail] = useState<RemedyDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadRemedies = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.handbook.remedies(600)
      setRemedies(data.results)
    } catch {
      setError("Не удалось загрузить препараты")
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    loadRemedies().then(() => {
      if (initialExpandedId != null) {
        openDetail(initialExpandedId)
      }
    })
  }, [])

  useEffect(() => {
    if (initialExpandedId != null) {
      openDetail(initialExpandedId)
    }
  }, [initialExpandedId])

  const openDetail = async (id: number) => {
    setDetailLoading(true)
    try {
      const data = await api.handbook.remedy(id)
      setDetail(data)
    } catch {
      setError("Не удалось загрузить детали препарата")
    }
    setDetailLoading(false)
  }

  const favorites = useAuthStore((s) => s.favorites)

  // Filter by name_lat, name_rus, and favorites
  const filtered = useMemo(() => {
    let result = remedies
    if (showFavoritesOnly) {
      result = result.filter((r) => favorites.has(`remedy:${r.id}`))
    }
    if (filter.trim()) {
      const q = filter.toLowerCase()
      result = result.filter(
        (r) =>
          r.name_lat.toLowerCase().includes(q) ||
          (r.name_rus || "").toLowerCase().includes(q)
      )
    }
    return result
  }, [filter, remedies, showFavoritesOnly, favorites])

  // Build alphabet index from filtered results
  const alphabet = useMemo(() => {
    const letters = new Set<string>()
    filtered.forEach((r) => {
      const first = r.name_lat[0]?.toUpperCase()
      if (first && /[A-Z]/.test(first)) letters.add(first)
    })
    return Array.from(letters).sort()
  }, [filtered])

  // Group filtered results by first letter
  const grouped = useMemo(() => {
    const groups: Record<string, Remedy[]> = {}
    filtered.forEach((r) => {
      const letter = r.name_lat[0]?.toUpperCase() || "#"
      const key = /[A-Z]/.test(letter) ? letter : "#"
      if (!groups[key]) groups[key] = []
      groups[key].push(r)
    })
    return groups
  }, [filtered])

  const scrollToLetter = (letter: string) => {
    const el = document.querySelector(`[data-letter="${letter}"]`)
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  // ─── Loading state ───
  if (loading) {
    return (
      <div id="remedies-tab" className="px-4 py-3" style={{ fontFamily: "var(--font-sans)" }}>
        <div className="skeleton h-9 w-full mb-3 rounded-lg" />
        <div className="skeleton h-4 w-32 mb-3 rounded" />
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="skeleton h-16 w-full mb-2 rounded-lg" />
        ))}
      </div>
    )
  }

  // ─── Error state ───
  if (error && remedies.length === 0) {
    return (
      <div id="remedies-tab" className="px-4 py-3 flex flex-col items-center justify-center min-h-[300px]" style={{ fontFamily: "var(--font-sans)" }}>
        <AlertCircle size={32} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
        <p className="text-sm mt-3 mb-4" style={{ color: "var(--text-secondary)" }}>{error}</p>
        <button
          onClick={loadRemedies}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium"
          style={{ background: "var(--accent-warm)", color: "#fff" }}
        >
          <RefreshCw size={16} strokeWidth={1.25} />
          Повторить
        </button>
      </div>
    )
  }

  // ─── Detail view ───
  if (detail) {
    return (
      <div id="remedy-detail" className="px-4 py-3" style={{ fontFamily: "var(--font-sans)" }}>
        <button
          onClick={() => setDetail(null)}
          className="flex items-center gap-1 text-sm mb-3 p-2 -ml-2"
          style={{ color: "var(--accent-warm)" }}
        >
          <ArrowLeft size={16} strokeWidth={1.25} />
          Назад к списку
        </button>

        <h2 className="text-lg font-semibold mb-0.5" style={{ color: "var(--text-primary)" }}>
          {detail.name_lat}
        </h2>
        {detail.name_rus && (
          <p className="text-sm mb-2" style={{ color: "var(--text-muted)" }}>
            {detail.name_rus}
          </p>
        )}
        {detail.summary && (
          <p className="text-sm mb-4 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {detail.summary}
          </p>
        )}

        {/* Symptoms by system */}
        {detail.symptoms.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs uppercase font-semibold tracking-wide mb-2" style={{ color: "var(--text-muted)" }}>
              Симптомы по системам
            </h3>
            {detail.symptoms.map((s, i) => (
              <div
                key={i}
                className="mb-2 rounded-lg border p-3"
                style={{ borderColor: "var(--border-subtle)", background: "var(--bg-secondary)" }}
              >
                <p className="text-xs font-semibold mb-1" style={{ color: "var(--accent-warm)" }}>
                  {s.system_name}
                </p>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {s.description}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Related conditions */}
        {detail.related_conditions.length > 0 && (
          <div>
            <h3 className="text-xs uppercase font-semibold tracking-wide mb-2" style={{ color: "var(--text-muted)" }}>
              Применяется при
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {detail.related_conditions.map((c) => (
                <span
                  key={c.id}
                  className="text-xs px-2 py-1 rounded-full"
                  style={{ background: "var(--accent-glow)", color: "var(--accent-warm)" }}
                >
                  {c.condition_name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ─── List view ───
  return (
    <div id="remedies-tab" className="relative" style={{ fontFamily: "var(--font-sans)" }}>
      <div className="px-4 py-3 pr-10">
        {/* Filter input */}
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Фильтр препаратов..."
          className="w-full rounded-lg border px-3 py-2 text-sm mb-3"
          style={{
            borderColor: "var(--border)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
          }}
        />

        <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
          {filtered.length} из {remedies.length} препаратов
        </p>

        {/* Detail loading indicator */}
        {detailLoading && (
          <div
            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 px-4 py-3 rounded-xl"
            style={{ background: "var(--bg-elevated)", boxShadow: "var(--shadow-lg)" }}
          >
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Загрузка...</p>
          </div>
        )}

        {/* Empty state */}
        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12">
            <SearchX size={32} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
            <p className="text-sm mt-3 mb-1" style={{ color: "var(--text-secondary)" }}>
              Ничего не найдено
            </p>
            <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
              Попробуйте другой запрос
            </p>
            {filter && (
              <button
                onClick={() => setFilter("")}
                className="px-4 py-2.5 rounded-lg text-sm font-medium"
                style={{ background: "var(--accent-warm)", color: "#fff" }}
              >
                Сбросить фильтр
              </button>
            )}
          </div>
        )}

        {/* Grouped list by letter */}
        {Object.entries(grouped)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([letter, items]) => (
            <div key={letter} data-letter={letter}>
              <div
                className="sticky top-0 z-10 text-xs font-semibold uppercase tracking-wide px-1 py-1.5"
                style={{ color: "var(--accent-warm)", background: "var(--bg-primary)" }}
              >
                {letter}
              </div>
              {items.map((r) => (
                <div
                  key={r.id}
                  data-entity-id={r.id}
                  onClick={() => openDetail(r.id)}
                  className="w-full text-left p-3 mb-1.5 rounded-lg border transition-opacity hover:opacity-80 cursor-pointer"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDetail(r.id) } }}
                  style={{ borderColor: "var(--border-subtle)", background: "var(--bg-secondary)" }}
                >
                  <div className="flex items-center justify-between">
                    <div className="min-w-0 flex-1">
                      <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                        {r.name_lat}
                      </span>
                      {r.name_rus && (
                        <span className="text-xs ml-2" style={{ color: "var(--text-muted)" }}>
                          {r.name_rus}
                        </span>
                      )}
                    </div>
                    <FavoriteButton entityType="remedy" entityId={r.id} onAuthRequired={onAuthRequired} />
                  </div>
                  {r.summary && (
                    <p className="text-xs mt-1 line-clamp-2" style={{ color: "var(--text-secondary)" }}>
                      {r.summary}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ))}
      </div>

      {/* Alphabet index — right sidebar */}
      {alphabet.length > 1 && !filter && (
        <nav
          id="alphabet-index"
          className="fixed right-0.5 top-1/2 -translate-y-1/2 z-20 flex flex-col items-center py-1"
          style={{ fontFamily: "var(--font-sans)" }}
        >
          {alphabet.map((letter) => (
            <button
              key={letter}
              onClick={() => scrollToLetter(letter)}
              className="w-6 h-5 flex items-center justify-center text-[10px] font-semibold"
              style={{ color: "var(--accent-warm)" }}
            >
              {letter}
            </button>
          ))}
        </nav>
      )}
    </div>
  )
}
