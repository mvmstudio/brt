"use client"

import { useState, useEffect } from "react"
import { Loader2 } from "lucide-react"
import { api, type EntityType, type RelationsResponse } from "@/lib/api"
import { RelationsList } from "./RelationsList"

interface RelationsSectionProps {
  entityType: EntityType
  entityId: number
  onNavigate?: (type: EntityType, id: number) => void
}

export function RelationsSection({ entityType, entityId, onNavigate }: RelationsSectionProps) {
  const [data, setData] = useState<RelationsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.handbook.relations(entityType, entityId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [entityType, entityId])

  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <Loader2 size={20} strokeWidth={1.25} className="animate-spin" style={{ color: "var(--text-muted)" }} />
      </div>
    )
  }

  if (!data || data.relations.length === 0) return null

  return <RelationsList relations={data.relations} onNavigate={onNavigate} />
}
