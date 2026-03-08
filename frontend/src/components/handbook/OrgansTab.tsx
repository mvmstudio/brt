"use client"

import { useState, useEffect, useCallback } from "react"
import { Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { api, type OrganPrep, type EntityType } from "@/lib/api"
import { FavoriteButton } from "./FavoriteButton"
import { RelationsSection } from "./RelationsSection"

interface OrgansTabProps {
  initialExpandedId?: number | null
  onAuthRequired?: () => void
  onNavigate?: (type: string, entityId: number) => void
  onRegisterRefresh?: (fn: () => Promise<void>) => void
}

export function OrgansTab({ initialExpandedId, onAuthRequired, onNavigate, onRegisterRefresh }: OrgansTabProps) {
  const [entries, setEntries] = useState<OrganPrep[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCat, setSelectedCat] = useState("")
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
      const data = await api.handbook.organs(cat || undefined, 500)
      setEntries(data.results)
      setCategories(data.categories)
    } catch {
      // silent
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    onRegisterRefresh?.(() => load(selectedCat || undefined))
  }, [onRegisterRefresh, selectedCat])

  const handleCatChange = (cat: string) => {
    setSelectedCat(cat)
    load(cat || undefined)
  }

  const filtered = (() => {
    let result = entries
    if (filter.trim()) {
      const q = filter.toLowerCase()
      result = result.filter((e) =>
        e.organ_name.toLowerCase().includes(q) ||
        (e.organ_name_lat || "").toLowerCase().includes(q)
      )
    }
    return result
  })()

  // Group by category
  const grouped = filtered.reduce<Record<string, OrganPrep[]>>((acc, e) => {
    const key = e.disease_category || "Без категории"
    if (!acc[key]) acc[key] = []
    acc[key].push(e)
    return acc
  }, {})

  return (
    <div id="organs-tab" className="px-4 py-3" style={{ fontFamily: "var(--font-sans)" }}>
      {/* Category select */}
      <select
        value={selectedCat}
        onChange={(e) => handleCatChange(e.target.value)}
        className="w-full rounded-lg border px-3 py-2 text-sm mb-2"
        style={{
          borderColor: "var(--border)",
          background: "var(--bg-secondary)",
          color: "var(--text-primary)",
        }}
      >
        <option value="">Все категории заболеваний</option>
        {categories.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>

      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Фильтр по названию органа..."
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
            {filtered.length} органных препаратов
          </p>

          {Object.entries(grouped).map(([cat, items]) => (
            <div key={cat} className="mb-4">
              <h3
                className="text-xs uppercase font-semibold tracking-wide mb-2 px-1"
                style={{ color: "var(--accent-warm)" }}
              >
                {cat}
              </h3>
              {items.map((e) => {
                const isExpanded = expandedIds.has(e.id)
                return (
                  <div
                    key={e.id}
                    data-entity-id={e.id}
                    className="mb-1 rounded-lg border overflow-hidden"
                    style={{
                      borderColor: isExpanded ? "var(--accent-warm)" : "var(--border-subtle)",
                      background: "var(--bg-secondary)",
                      boxShadow: isExpanded ? "0 0 0 1px var(--accent-warm), 0 0 12px var(--accent-glow)" : "none",
                    }}
                  >
                    <div
                      onClick={() => toggle(e.id)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-left cursor-pointer"
                      role="button"
                      tabIndex={0}
                      onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(e.id) } }}
                    >
                      <div className="min-w-0 flex-1">
                        <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                          {e.organ_name}
                        </span>
                        {e.organ_name_lat && e.organ_name_lat !== e.organ_name && (
                          <span className="text-xs ml-1.5" style={{ color: "var(--text-muted)" }}>
                            {e.organ_name_lat}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <FavoriteButton entityType="organ" entityId={e.id} onAuthRequired={onAuthRequired} />
                        {isExpanded
                          ? <ChevronUp size={14} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                          : <ChevronDown size={14} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                        }
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="px-3 pb-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                        <RelationsSection
                          entityType="organ"
                          entityId={e.id}
                          onNavigate={onNavigate as (type: EntityType, id: number) => void}
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </>
      )}
    </div>
  )
}
