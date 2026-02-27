"use client"

import { useState, useEffect, useCallback } from "react"
import { Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { api, type EtiologyEntry } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"
import { SourceBadge } from "./SourceBadge"
import { FavoriteButton } from "./FavoriteButton"

const AGENT_TYPE_LABELS: Record<string, string> = {
  virus: "Вирусы",
  bacteria_cocci: "Бактерии (кокки)",
  bacteria_bacilli: "Бактерии (палочки)",
  parasite_fungi: "Паразиты и грибы",
}

interface EtiologyTabProps {
  initialExpandedId?: number | null
  onAuthRequired?: () => void
  showFavoritesOnly?: boolean
}

export function EtiologyTab({ initialExpandedId, onAuthRequired, showFavoritesOnly }: EtiologyTabProps) {
  const [entries, setEntries] = useState<EtiologyEntry[]>([])
  const [systems, setSystems] = useState<string[]>([])
  const [agentTypes, setAgentTypes] = useState<string[]>([])
  const [selectedSystem, setSelectedSystem] = useState("")
  const [selectedType, setSelectedType] = useState("")
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

  const load = async (system?: string, type?: string) => {
    setLoading(true)
    try {
      const data = await api.handbook.etiology(system || undefined, type || undefined, 1000)
      setEntries(data.results)
      setSystems(data.disease_systems)
      setAgentTypes(data.agent_types)
    } catch {
      // silent
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleSystemChange = (sys: string) => {
    setSelectedSystem(sys)
    load(sys || undefined, selectedType || undefined)
  }

  const handleTypeChange = (type: string) => {
    setSelectedType(type)
    load(selectedSystem || undefined, type || undefined)
  }

  const favorites = useAuthStore((s) => s.favorites)

  const filtered = (() => {
    let result = entries
    if (showFavoritesOnly) {
      result = result.filter((e) => favorites.has(`etiology:${e.id}`))
    }
    if (filter.trim()) {
      const q = filter.toLowerCase()
      result = result.filter((e) =>
        e.agent_name.toLowerCase().includes(q) ||
        (e.agent_name_rus || "").toLowerCase().includes(q) ||
        e.disease_system.toLowerCase().includes(q)
      )
    }
    return result
  })()

  // Group filtered entries by disease system
  const grouped = filtered.reduce<Record<string, EtiologyEntry[]>>((acc, e) => {
    if (!acc[e.disease_system]) acc[e.disease_system] = []
    acc[e.disease_system].push(e)
    return acc
  }, {})

  return (
    <div id="etiology-tab" className="px-4 py-3" style={{ fontFamily: "var(--font-sans)" }}>
      {/* System filter */}
      <select
        value={selectedSystem}
        onChange={(e) => handleSystemChange(e.target.value)}
        className="w-full rounded-lg border px-3 py-2 text-sm mb-2"
        style={{
          borderColor: "var(--border)",
          background: "var(--bg-secondary)",
          color: "var(--text-primary)",
        }}
      >
        <option value="">Все системы органов</option>
        {systems.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      {/* Agent type pills */}
      <div className="flex gap-1.5 overflow-x-auto mb-3 pb-1 scrollbar-none">
        <button
          onClick={() => handleTypeChange("")}
          className="shrink-0 px-2.5 py-1 rounded-full text-xs font-medium"
          style={{
            background: !selectedType ? "var(--accent-warm)" : "transparent",
            color: !selectedType ? "#fff" : "var(--text-secondary)",
            border: !selectedType ? "none" : "1px solid var(--border)",
          }}
        >
          Все типы
        </button>
        {agentTypes.map((t) => (
          <button
            key={t}
            onClick={() => handleTypeChange(t)}
            className="shrink-0 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{
              background: selectedType === t ? "var(--accent-warm)" : "transparent",
              color: selectedType === t ? "#fff" : "var(--text-secondary)",
              border: selectedType === t ? "none" : "1px solid var(--border)",
            }}
          >
            {AGENT_TYPE_LABELS[t] || t}
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
            {filtered.length} записей
          </p>

          {Object.entries(grouped).map(([system, items]) => (
            <div key={system} className="mb-4">
              <h3
                className="text-xs uppercase font-semibold tracking-wide mb-2 px-1"
                style={{ color: "var(--accent-warm)" }}
              >
                {system}
              </h3>
              {items.map((e) => {
                const isExpanded = expandedIds.has(e.id)
                const hasExtra = e.description || (e.remedies_list && e.remedies_list.length > 0)
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
                      onClick={() => hasExtra && toggle(e.id)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-left cursor-pointer"
                      role="button"
                      tabIndex={0}
                      onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); hasExtra && toggle(e.id) } }}
                    >
                      <div className="min-w-0 flex-1">
                        <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                          {e.agent_name}
                        </span>
                        {e.agent_name_rus && (
                          <span className="text-xs ml-1.5" style={{ color: "var(--text-muted)" }}>
                            ({e.agent_name_rus})
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <FavoriteButton entityType="etiology" entityId={e.id} onAuthRequired={onAuthRequired} />
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded"
                          style={{ background: "var(--accent-glow)", color: "var(--accent-warm)" }}
                        >
                          {AGENT_TYPE_LABELS[e.agent_type]?.split(" ")[0] || e.agent_type}
                        </span>
                        {hasExtra && (isExpanded
                          ? <ChevronUp size={14} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                          : <ChevronDown size={14} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
                        )}
                      </div>
                    </div>

                    {isExpanded && hasExtra && (
                      <div className="px-3 pb-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                        {e.description && (
                          <p className="text-xs leading-relaxed mt-2 mb-2" style={{ color: "var(--text-secondary)" }}>
                            {e.description}
                          </p>
                        )}
                        {e.remedies_list && e.remedies_list.length > 0 && (
                          <>
                            <div className="flex items-center gap-1 mb-1.5">
                              <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                                Препараты ({e.remedies_list.length})
                              </span>
                              <SourceBadge source={e.content_source} />
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {e.remedies_list.map((name, i) => (
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
            </div>
          ))}
        </>
      )}
    </div>
  )
}
