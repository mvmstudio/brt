"use client"

import { useState, useEffect, useCallback } from "react"
import { Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { api, type Nosode } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"
import { SourceBadge } from "./SourceBadge"
import { FavoriteButton } from "./FavoriteButton"

const CATEGORY_LABELS: Record<string, string> = {
  bacteria_cocci: "Бактерии (кокки)",
  bacteria_bacilli: "Бактерии (палочки)",
  virus: "Вирусы",
  protozoa_helminths_fungi: "Простейшие, гельминты, грибы",
}

interface NosodesTabProps {
  initialExpandedId?: number | null
  onAuthRequired?: () => void
  showFavoritesOnly?: boolean
}

export function NosodesTab({ initialExpandedId, onAuthRequired, showFavoritesOnly }: NosodesTabProps) {
  const [nosodes, setNosodes] = useState<Nosode[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCat, setSelectedCat] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState("")
  const [expandedIds, setExpandedIds] = useState<Set<number>>(
    initialExpandedId != null ? new Set([initialExpandedId]) : new Set()
  )

  const toggle = useCallback((id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }, [])

  useEffect(() => {
    if (initialExpandedId != null) {
      setExpandedIds((prev) => new Set(prev).add(initialExpandedId))
    }
  }, [initialExpandedId])

  useEffect(() => {
    if (initialExpandedId != null && !loading) {
      const timer = setTimeout(() => {
        const el = document.querySelector(`[data-entity-id="${initialExpandedId}"]`)
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" })
      }, 150)
      return () => clearTimeout(timer)
    }
  }, [initialExpandedId, loading])

  const load = async (cat?: string) => {
    setLoading(true)
    try {
      const data = await api.handbook.nosodes(cat || undefined, 500)
      setNosodes(data.results)
      setCategories(data.categories)
    } catch {
      // silent
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleCatChange = (cat: string) => {
    setSelectedCat(cat)
    load(cat || undefined)
  }

  const favorites = useAuthStore((s) => s.favorites)

  const filtered = (() => {
    let result = nosodes
    if (showFavoritesOnly) {
      result = result.filter((n) => favorites.has(`nosode:${n.id}`))
    }
    if (filter.trim()) {
      const q = filter.toLowerCase()
      result = result.filter((n) =>
        n.name_lat.toLowerCase().includes(q) ||
        (n.name_rus || "").toLowerCase().includes(q)
      )
    }
    return result
  })()

  return (
    <div id="nosodes-tab" className="px-4 py-3" style={{ fontFamily: "var(--font-sans)" }}>
      {/* Category filter */}
      <div className="flex gap-1.5 overflow-x-auto mb-3 pb-1 scrollbar-none">
        <button
          onClick={() => handleCatChange("")}
          className="shrink-0 px-2.5 py-1 rounded-full text-xs font-medium"
          style={{
            background: !selectedCat ? "var(--accent-warm)" : "transparent",
            color: !selectedCat ? "#fff" : "var(--text-secondary)",
            border: !selectedCat ? "none" : "1px solid var(--border)",
          }}
        >
          Все
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => handleCatChange(cat)}
            className="shrink-0 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{
              background: selectedCat === cat ? "var(--accent-warm)" : "transparent",
              color: selectedCat === cat ? "#fff" : "var(--text-secondary)",
              border: selectedCat === cat ? "none" : "1px solid var(--border)",
            }}
          >
            {CATEGORY_LABELS[cat] || cat}
          </button>
        ))}
      </div>

      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Фильтр по названию..."
        className="w-full rounded-lg border px-3 py-2 text-sm mb-3"
        style={{
          borderColor: "var(--border)",
          background: "var(--bg-secondary)",
          color: "var(--text-primary)",
        }}
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 size={24} strokeWidth={1.25} className="animate-spin" style={{ color: "var(--text-muted)" }} />
        </div>
      ) : (
        <>
          <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
            {filtered.length} нозодов
          </p>
          {filtered.map((n) => {
            const isExpanded = expandedIds.has(n.id)
            const hasExtra = n.description || (n.remedies_list && n.remedies_list.length > 0)
            return (
              <div
                key={n.id}
                data-entity-id={n.id}
                className="mb-1.5 rounded-lg border overflow-hidden"
                style={{
                  borderColor: isExpanded ? "var(--accent-warm)" : "var(--border-subtle)",
                  background: "var(--bg-secondary)",
                  boxShadow: isExpanded ? "0 0 0 1px var(--accent-warm), 0 0 12px var(--accent-glow)" : "none",
                }}
              >
                <div
                  onClick={() => hasExtra && toggle(n.id)}
                  className="w-full flex items-center gap-3 p-2.5 text-left cursor-pointer"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); hasExtra && toggle(n.id) } }}
                >
                  {n.number && (
                    <span
                      className="text-xs font-medium shrink-0 w-7 text-center"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {n.number}
                    </span>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
                      {n.name_lat}
                    </p>
                    {n.name_rus && (
                      <p className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>
                        {n.name_rus}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <FavoriteButton entityType="nosode" entityId={n.id} onAuthRequired={onAuthRequired} />
                    {n.category && (
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: "var(--accent-glow)", color: "var(--accent-warm)" }}
                      >
                        {CATEGORY_LABELS[n.category]?.split(" ")[0] || n.category}
                      </span>
                    )}
                    {hasExtra && (isExpanded
                      ? <ChevronUp size={14} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                      : <ChevronDown size={14} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                    )}
                  </div>
                </div>

                {isExpanded && hasExtra && (
                  <div className="px-3 pb-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                    {n.description && (
                      <p className="text-xs leading-relaxed mt-2 mb-2" style={{ color: "var(--text-secondary)" }}>
                        {n.description}
                      </p>
                    )}
                    {n.remedies_list && n.remedies_list.length > 0 && (
                      <>
                        <div className="flex items-center gap-1 mb-1.5">
                          <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                            Препараты ({n.remedies_list.length})
                          </span>
                          <SourceBadge source={n.content_source} />
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {n.remedies_list.map((name, i) => (
                            <span
                              key={i}
                              className="text-xs px-2 py-1 rounded-full"
                              style={{ background: "var(--accent-glow)", color: "var(--accent-warm)" }}
                            >
                              {name}
                            </span>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </>
      )}
    </div>
  )
}
