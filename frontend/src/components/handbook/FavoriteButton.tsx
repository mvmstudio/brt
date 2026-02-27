"use client"

import { useCallback } from "react"
import { Star } from "lucide-react"
import { useAuthStore } from "@/stores/auth"
import { api } from "@/lib/api"

interface FavoriteButtonProps {
  entityType: string
  entityId: number
  onAuthRequired?: () => void
}

export function FavoriteButton({ entityType, entityId, onAuthRequired }: FavoriteButtonProps) {
  const token = useAuthStore((s) => s.token)
  const isFav = useAuthStore((s) => s.isFavorite(entityType, entityId))
  const addFavorite = useAuthStore((s) => s.addFavorite)
  const removeFavorite = useAuthStore((s) => s.removeFavorite)

  const handleClick = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation()
      if (!token) {
        onAuthRequired?.()
        return
      }
      try {
        if (isFav) {
          removeFavorite(entityType, entityId)
          await api.favorites.remove(entityType, entityId)
        } else {
          addFavorite(entityType, entityId)
          await api.favorites.add(entityType, entityId)
        }
      } catch {
        // Revert on error
        if (isFav) {
          addFavorite(entityType, entityId)
        } else {
          removeFavorite(entityType, entityId)
        }
      }
    },
    [token, isFav, entityType, entityId, addFavorite, removeFavorite, onAuthRequired]
  )

  return (
    <button
      onClick={handleClick}
      className="shrink-0 w-11 h-11 flex items-center justify-center rounded-lg"
      aria-label={isFav ? "Remove from favorites" : "Add to favorites"}
    >
      <Star
        size={20}
        strokeWidth={1.25}
        fill={isFav ? "var(--accent-warm)" : "none"}
        style={{ color: isFav ? "var(--accent-warm)" : "var(--text-muted)" }}
      />
    </button>
  )
}
