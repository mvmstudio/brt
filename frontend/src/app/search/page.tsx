"use client"

import { useState } from "react"
import { api, type SearchResult } from "@/lib/api"
import { Search, ArrowLeft, Loader2 } from "lucide-react"
import Link from "next/link"
import { useReaderStore } from "@/stores/reader"
import { useRouter } from "next/navigation"
import { SnippetText } from "@/components/search/SnippetText"

export default function SearchPage() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const { setPage } = useReaderStore()
  const router = useRouter()

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setSearched(true)
    try {
      const data = await api.search(query.trim())
      setResults(data.results)
    } catch {
      setResults([])
    }
    setLoading(false)
  }

  const goToPage = (pageNum: number) => {
    setPage(pageNum)
    router.push("/")
  }

  return (
    <div className="flex flex-col h-dvh" style={{ background: "var(--bg-primary)" }}>
      <header
        id="search-header"
        className="flex items-center gap-2 px-4 py-3 border-b shrink-0"
        style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
      >
        <Link href="/" className="p-1 rounded hover:opacity-70">
          <ArrowLeft size={20} strokeWidth={1.25} />
        </Link>
        <form onSubmit={handleSearch} className="flex-1 flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по книге..."
            autoFocus
            className="flex-1 rounded-lg border px-3 py-2 text-sm"
            style={{
              borderColor: "var(--border)",
              background: "var(--bg-primary)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            className="p-2 rounded-lg"
            style={{ background: "var(--accent)", color: "white" }}
          >
            <Search size={18} strokeWidth={1.25} />
          </button>
        </form>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4">
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

        {!loading && results.map((r, i) => (
          <button
            key={i}
            onClick={() => goToPage(r.page_num)}
            className="w-full text-left p-3 mb-2 rounded-lg border hover:opacity-80 transition-opacity"
            style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium" style={{ color: "var(--accent)" }}>
                Стр. {r.page_num}
              </span>
              {r.chapter && (
                <span className="text-xs truncate max-w-[200px]" style={{ color: "var(--text-muted)" }}>
                  {r.chapter}
                </span>
              )}
            </div>
            <SnippetText html={r.snippet} />
          </button>
        ))}
      </div>
    </div>
  )
}
