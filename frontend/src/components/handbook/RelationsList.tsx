"use client"

import { type RelationNode, type EntityType } from "@/lib/api"

const TYPE_COLORS: Record<EntityType, string> = {
  condition: "#4A90D9",
  remedy: "#5CB85C",
  nosode: "#9B59B6",
  etiology: "#E67E22",
  organ: "#E74C3C",
}

const TYPE_LABELS: Record<EntityType, string> = {
  condition: "Заболевания",
  remedy: "Препараты",
  nosode: "Нозоды",
  etiology: "Этиология",
  organ: "Органы",
}

interface RelationsListProps {
  relations: RelationNode[]
  onNavigate?: (type: EntityType, id: number) => void
}

export function RelationsList({ relations, onNavigate }: RelationsListProps) {
  // Group by type
  const grouped: Partial<Record<EntityType, RelationNode[]>> = {}
  for (const rel of relations) {
    const t = rel.type
    if (!grouped[t]) grouped[t] = []
    grouped[t]!.push(rel)
  }

  const entries = Object.entries(grouped) as [EntityType, RelationNode[]][]
  if (entries.length === 0) return null

  return (
    <div id="relations-list" className="mt-3">
      <h3
        className="text-xs uppercase font-semibold tracking-wide mb-2"
        style={{ color: "var(--text-muted)" }}
      >
        Связи
      </h3>
      {entries.map(([type, items]) => (
        <div key={type} className="mb-2.5">
          <span
            className="text-[10px] font-medium"
            style={{ color: TYPE_COLORS[type] }}
          >
            {TYPE_LABELS[type]} ({items.length})
          </span>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {items.map((item, i) => (
              <button
                key={`${type}-${i}`}
                onClick={() => item.id != null && onNavigate?.(item.type, item.id)}
                disabled={item.id == null}
                className="text-xs px-2.5 py-1 rounded-full transition-opacity hover:opacity-80 disabled:opacity-50 disabled:cursor-default"
                style={{
                  background: `${TYPE_COLORS[type]}18`,
                  color: TYPE_COLORS[type],
                  border: `1px solid ${TYPE_COLORS[type]}30`,
                }}
              >
                {item.name}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
