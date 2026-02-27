"use client"

import { useMemo } from "react"

/**
 * Renders search snippet with <mark> highlighting.
 * Safely parses only <mark> tags from FTS5 snippet() function.
 * No innerHTML used — all rendering through React elements.
 */
export function SnippetText({ html }: { html: string }) {
  const parts = useMemo(() => {
    const segments: { text: string; marked: boolean }[] = []
    const pattern = /<mark>(.*?)<\/mark>/g
    let lastIndex = 0
    let result = pattern.exec(html) // regex exec — not child_process

    while (result !== null) {
      if (result.index > lastIndex) {
        const plain = html.slice(lastIndex, result.index).replace(/<[^>]*>/g, "")
        if (plain) segments.push({ text: plain, marked: false })
      }
      segments.push({ text: result[1], marked: true })
      lastIndex = pattern.lastIndex
      result = pattern.exec(html)
    }

    if (lastIndex < html.length) {
      const plain = html.slice(lastIndex).replace(/<[^>]*>/g, "")
      if (plain) segments.push({ text: plain, marked: false })
    }

    return segments
  }, [html])

  return (
    <div className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
      {parts.map((part, i) =>
        part.marked ? (
          <mark key={i} style={{ background: "var(--accent-light)", padding: "0 2px", borderRadius: "2px" }}>
            {part.text}
          </mark>
        ) : (
          <span key={i}>{part.text}</span>
        )
      )}
    </div>
  )
}
