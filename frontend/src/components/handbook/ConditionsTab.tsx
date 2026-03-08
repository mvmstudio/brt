"use client"

import { useState, useEffect, useCallback } from "react"
import { Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { api, type Condition, type ConditionDetail, type EntityType } from "@/lib/api"
import { FavoriteButton } from "./FavoriteButton"
import { RelationsSection } from "./RelationsSection"

interface ConditionsTabProps {
  initialExpandedId?: number | null
  onAuthRequired?: () => void
  onNavigate?: (type: string, entityId: number) => void
  onRegisterRefresh?: (fn: () => Promise<void>) => void
}

export function ConditionsTab({ initialExpandedId, onAuthRequired, onNavigate, onRegisterRefresh }: ConditionsTabProps) {
  const [conditions, setConditions] = useState<Condition[]>([])
  const [filtered, setFiltered] = useState<Condition[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState("")
  const [expandedIds, setExpandedIds] = useState<Set<number>>(
    initialExpandedId != null ? new Set([initialExpandedId]) : new Set()
  )
  const [details, setDetails] = useState<Record<number, ConditionDetail>>({})
  const [detailLoading, setDetailLoading] = useState<Set<number>>(new Set())

  const toggle = useCallback((id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
        // Load detail if not cached
        if (!details[id]) loadDetail(id)
      }
      return next
    })
  }, [details])

  const loadDetail = async (id: number) => {
    setDetailLoading((prev) => new Set(prev).add(id))
    try {
      const data = await api.handbook.condition(id)
      setDetails((prev) => ({ ...prev, [id]: data }))
    } catch { /* silent */ }
    setDetailLoading((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.handbook.conditions(500)
      setConditions(data.results)
      setFiltered(data.results)
    } catch { /* silent */ }
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    onRegisterRefresh?.(loadData)
  }, [onRegisterRefresh, loadData])

  useEffect(() => {
    if (initialExpandedId != null) {
      setExpandedIds((prev) => new Set(prev).add(initialExpandedId))
      if (!details[initialExpandedId]) loadDetail(initialExpandedId)
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

  useEffect(() => {
    let result = conditions
    if (filter.trim()) {
      const q = filter.toLowerCase()
      result = result.filter((c) => c.condition_name.toLowerCase().includes(q))
    }
    setFiltered(result)
  }, [filter, conditions])

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 size={24} strokeWidth={1.25} className="animate-spin" style={{ color: "var(--text-muted)" }} />
      </div>
    )
  }

  return (
    <div id="conditions-tab" className="px-4 py-3" style={{ fontFamily: "var(--font-sans)" }}>
      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Фильтр заболеваний..."
        className="w-full rounded-lg border px-3 py-2 text-sm mb-3"
        style={{
          borderColor: "var(--border)",
          background: "var(--bg-secondary)",
          color: "var(--text-primary)",
        }}
      />

      <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
        {filtered.length} из {conditions.length} заболеваний
      </p>

      {filtered.map((c) => {
        const isExpanded = expandedIds.has(c.id)
        const detail = details[c.id]
        const isDetailLoading = detailLoading.has(c.id)
        return (
          <div
            key={c.id}
            data-entity-id={c.id}
            className="mb-2 rounded-lg border overflow-hidden"
            style={{
              borderColor: isExpanded ? "var(--accent-warm)" : "var(--border-subtle)",
              background: "var(--bg-secondary)",
              boxShadow: isExpanded ? "0 0 0 1px var(--accent-warm), 0 0 12px var(--accent-glow)" : "none",
            }}
          >
            <div
              onClick={() => toggle(c.id)}
              className="w-full flex items-center justify-between px-3 py-2.5 text-left cursor-pointer"
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(c.id) } }}
            >
              <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {c.condition_name}
              </span>
              <div className="flex items-center gap-1 shrink-0">
                <FavoriteButton entityType="condition" entityId={c.id} onAuthRequired={onAuthRequired} />
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {c.remedies.length}
                </span>
                {isExpanded ? (
                  <ChevronUp size={16} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                ) : (
                  <ChevronDown size={16} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                )}
              </div>
            </div>

            {isExpanded && (
              <div className="px-3 pb-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                <div className="flex items-center gap-1 mt-2 mb-1.5">
                  <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                    Препараты ({c.remedies.length})
                  </span>
                </div>

                {isDetailLoading ? (
                  <div className="flex justify-center py-3">
                    <Loader2 size={16} strokeWidth={1.25} className="animate-spin" style={{ color: "var(--text-muted)" }} />
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {detail ? (
                      detail.remedies_details.map((rd, i) => (
                        rd.id != null ? (
                          <button
                            key={i}
                            onClick={() => onNavigate?.("remedy", rd.id!)}
                            className="text-xs px-2 py-1 rounded-full transition-opacity hover:opacity-80"
                            style={{ background: "rgba(92, 184, 92, 0.15)", color: "#5CB85C" }}
                          >
                            {rd.name_lat}
                          </button>
                        ) : (
                          <span
                            key={i}
                            className="text-xs px-2 py-1 rounded-full opacity-50"
                            style={{ background: "var(--accent-glow)", color: "var(--text-muted)" }}
                          >
                            {rd.name_lat}
                          </span>
                        )
                      ))
                    ) : (
                      c.remedies.map((name, i) => (
                        <span
                          key={i}
                          className="text-xs px-2 py-1 rounded-full"
                          style={{ background: "var(--accent-glow)", color: "var(--accent-warm)" }}
                        >
                          {name}
                        </span>
                      ))
                    )}
                  </div>
                )}

                <RelationsSection
                  entityType="condition"
                  entityId={c.id}
                  onNavigate={onNavigate as (type: EntityType, id: number) => void}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
