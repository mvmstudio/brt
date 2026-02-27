"use client"

import { useState } from "react"
import { Search, Loader2, ArrowRight } from "lucide-react"
import { api, type HandbookSearchResult } from "@/lib/api"
import { SnippetText } from "@/components/search/SnippetText"

const TYPE_LABELS: Record<string, string> = {
  remedy: "Препарат",
  remedy_symptom: "Симптом",
  condition: "Заболевание",
  nosode: "Нозод",
  etiology: "Этиология",
  organ: "Орган",
}

interface HandbookSearchProps {
  onNavigate?: (type: string, entityId: number) => void
}

export function HandbookSearch({ onNavigate }: HandbookSearchProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<HandbookSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setSearched(true)
    try {
      const data = await api.handbook.search(query.trim(), 30)
      setResults(data.results)
    } catch {
      setResults([])
    }
    setLoading(false)
  }

  const handleClick = (r: HandbookSearchResult) => {
    if (!onNavigate) return
    // remedy_symptom navigates to the remedy
    const type = r.type === "remedy_symptom" ? "remedy" : r.type
    onNavigate(type, r.entity_id)
  }

  const isClickable = (type: string) =>
    !!onNavigate && ["condition", "remedy", "remedy_symptom", "nosode", "etiology", "organ"].includes(type)

  return (
    <div id="handbook-search" className="px-4 py-4" style={{ fontFamily: "var(--font-sans)" }}>
      <form onSubmit={handleSearch} className="flex gap-2 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Поиск по справочнику..."
          autoFocus
          className="flex-1 rounded-lg border px-3 py-2 text-sm"
          style={{
            borderColor: "var(--border)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
          }}
        />
        <button
          type="submit"
          className="p-2.5 rounded-lg shrink-0"
          style={{ background: "var(--accent-warm)", color: "#fff" }}
        >
          <Search size={18} strokeWidth={1.25} />
        </button>
      </form>

      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 size={24} strokeWidth={1.25} className="animate-spin" style={{ color: "var(--text-muted)" }} />
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <p className="text-center py-12 text-sm" style={{ color: "var(--text-muted)" }}>
          Ничего не найдено
        </p>
      )}

      {!loading &&
        results.map((r, i) => {
          const clickable = isClickable(r.type)
          return (
            <button
              key={i}
              type="button"
              onClick={() => clickable && handleClick(r)}
              disabled={!clickable}
              className="w-full text-left p-3 mb-2 rounded-lg border transition-colors"
              style={{
                borderColor: "var(--border-subtle)",
                background: "var(--bg-secondary)",
                cursor: clickable ? "pointer" : "default",
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="text-[10px] uppercase font-semibold tracking-wide px-1.5 py-0.5 rounded shrink-0"
                  style={{ background: "var(--accent-glow)", color: "var(--accent-warm)" }}
                >
                  {TYPE_LABELS[r.type] || r.type}
                </span>
                <span className="text-xs font-medium truncate flex-1" style={{ color: "var(--text-primary)" }}>
                  {r.name}
                </span>
                {clickable && (
                  <ArrowRight size={14} strokeWidth={1.25} className="shrink-0" style={{ color: "var(--text-muted)" }} />
                )}
              </div>
              <SnippetText html={r.snippet} />
            </button>
          )
        })}

      {!loading && !searched && (
        <p className="text-center py-8 text-sm" style={{ color: "var(--text-muted)" }}>
          Поиск по заболеваниям, препаратам, симптомам, нозодам и органам
        </p>
      )}
    </div>
  )
}
