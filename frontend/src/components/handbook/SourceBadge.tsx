"use client"

import { BookOpen, Sparkles } from "lucide-react"

interface SourceBadgeProps {
  source: string | null
}

export function SourceBadge({ source }: SourceBadgeProps) {
  if (!source) return null

  const config = {
    book: { icon: BookOpen, label: "Книга", color: "var(--text-muted)" },
    llm: { icon: Sparkles, label: "AI", color: "var(--accent-warm)" },
    hybrid: { icon: Sparkles, label: "Книга+AI", color: "var(--accent-warm)" },
  }[source]

  if (!config) return null

  const Icon = config.icon

  return (
    <span
      className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded"
      style={{ color: config.color, opacity: 0.7 }}
    >
      <Icon size={10} strokeWidth={1.25} />
      {config.label}
    </span>
  )
}
