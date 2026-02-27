import { create } from "zustand"
import { persist } from "zustand/middleware"

interface AuthUser {
  id: number
  username: string
}

interface FavoriteKey {
  entity_type: string
  entity_id: number
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  favorites: Set<string> // "type:id" keys for fast lookup

  setAuth: (token: string, user: AuthUser) => void
  logout: () => void
  setFavorites: (items: FavoriteKey[]) => void
  isFavorite: (type: string, id: number) => boolean
  addFavorite: (type: string, id: number) => void
  removeFavorite: (type: string, id: number) => void
}

const favKey = (type: string, id: number) => `${type}:${id}`

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      favorites: new Set(),

      setAuth: (token, user) => set({ token, user }),

      logout: () => set({ token: null, user: null, favorites: new Set() }),

      setFavorites: (items) =>
        set({ favorites: new Set(items.map((f) => favKey(f.entity_type, f.entity_id))) }),

      isFavorite: (type, id) => get().favorites.has(favKey(type, id)),

      addFavorite: (type, id) => {
        const next = new Set(get().favorites)
        next.add(favKey(type, id))
        set({ favorites: next })
      },

      removeFavorite: (type, id) => {
        const next = new Set(get().favorites)
        next.delete(favKey(type, id))
        set({ favorites: next })
      },
    }),
    {
      name: "brt-auth",
      storage: {
        getItem: (name) => {
          const str = localStorage.getItem(name)
          if (!str) return null
          const parsed = JSON.parse(str)
          // Restore Set from array
          if (parsed?.state?.favorites) {
            parsed.state.favorites = new Set(parsed.state.favorites)
          }
          return parsed
        },
        setItem: (name, value) => {
          // Serialize Set to array for JSON storage
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const v = value as any
          const copy = { ...v, state: { ...v.state } }
          if (v.state.favorites instanceof Set) {
            copy.state.favorites = Array.from(v.state.favorites)
          }
          localStorage.setItem(name, JSON.stringify(copy))
        },
        removeItem: (name) => localStorage.removeItem(name),
      },
    }
  )
)
