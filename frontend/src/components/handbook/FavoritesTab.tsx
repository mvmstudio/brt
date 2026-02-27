"use client"

import { useState, useEffect, useCallback } from "react"
import { Loader2, Star, Stethoscope, Pill, Bug, Microscope, Heart } from "lucide-react"
import { api, type FavoriteItem } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"
import { FavoriteButton } from "./FavoriteButton"

const TYPE_CONFIG: Record<string, { label: string; icon: typeof Stethoscope; entityType: string }> = {
  condition: { label: "Болезни", icon: Stethoscope, entityType: "condition" },
  remedy: { label: "Препараты", icon: Pill, entityType: "remedy" },
  nosode: { label: "Нозоды", icon: Bug, entityType: "nosode" },
  etiology: { label: "Этиология", icon: Microscope, entityType: "etiology" },
  organ: { label: "Органы", icon: Heart, entityType: "organ" },
}

const TYPE_ORDER = ["condition", "remedy", "nosode", "etiology", "organ"]

interface FavoritesTabProps {
  onNavigate?: (type: string, entityId: number) => void
  onAuthRequired?: () => void
}

export function FavoritesTab({ onNavigate, onAuthRequired }: FavoritesTabProps) {
  const token = useAuthStore((s) => s.token)
  const [items, setItems] = useState<FavoriteItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadFavorites = useCallback(async () => {
    if (!token) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await api.favorites.list(undefined, true)
      setItems(data.favorites)
      useAuthStore.getState().setFavorites(data.favorites)
    } catch {
      setError("Не удалось загрузить избранное")
    }
    setLoading(false)
  }, [token])

  useEffect(() => {
    loadFavorites()
  }, [loadFavorites])

  if (!token) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
        <Star size={32} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
        <p className="mt-3 text-sm" style={{ color: "var(--text-muted)" }}>
          Войдите, чтобы сохранять избранное
        </p>
        <button
          onClick={onAuthRequired}
          className="mt-4 px-4 py-2.5 rounded-lg text-sm font-medium"
          style={{ background: "var(--accent-warm)", color: "#fff" }}
        >
          Войти
        </button>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 size={24} strokeWidth={1.25} className="animate-spin" style={{ color: "var(--text-muted)" }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>{error}</p>
        <button
          onClick={loadFavorites}
          className="mt-4 px-4 py-2.5 rounded-lg text-sm font-medium"
          style={{ background: "var(--accent-warm)", color: "#fff" }}
        >
          Повторить
        </button>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
        <Star size={32} strokeWidth={1.25} style={{ color: "var(--text-muted)" }} />
        <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Нет избранного
        </p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Нажмите звёздочку рядом с любой сущностью, чтобы добавить в избранное
        </p>
      </div>
    )
  }

  // Group by entity_type
  const grouped: Record<string, FavoriteItem[]> = {}
  for (const item of items) {
    if (!grouped[item.entity_type]) grouped[item.entity_type] = []
    grouped[item.entity_type].push(item)
  }

  return (
    <div className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
      {TYPE_ORDER.filter((t) => grouped[t]?.length).map((type) => {
        const config = TYPE_CONFIG[type]
        if (!config) return null
        const group = grouped[type]
        const Icon = config.icon

        return (
          <section key={type} className="px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <Icon size={16} strokeWidth={1.25} style={{ color: "var(--accent-warm)" }} />
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                {config.label}
              </h3>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {group.length}
              </span>
            </div>

            <div className="space-y-1">
              {group.map((item) => (
                <div
                  key={`${item.entity_type}:${item.entity_id}`}
                  className="flex items-center gap-2 rounded-lg px-3 py-2.5 cursor-pointer hover:opacity-80 transition-opacity"
                  style={{ background: "var(--bg-secondary)" }}
                  onClick={() => onNavigate?.(item.entity_type, item.entity_id)}
                >
                  <span
                    className="flex-1 text-sm truncate"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {item.entity_name || `#${item.entity_id}`}
                  </span>
                  <FavoriteButton
                    entityType={item.entity_type}
                    entityId={item.entity_id}
                    onAuthRequired={onAuthRequired}
                    onToggle={loadFavorites}
                  />
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
