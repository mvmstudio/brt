"use client"

import { useState, useEffect, useCallback } from "react"
import { LogIn } from "lucide-react"
import { useAuthStore } from "@/stores/auth"
import { api } from "@/lib/api"

export function AuthGate({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  const setAuth = useAuthStore((s) => s.setAuth)
  const [hydrated, setHydrated] = useState(false)

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setHydrated(true)
  }, [])

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      setError(null)
      setLoading(true)

      try {
        const data = await api.auth.login(username, password)
        setAuth(data.token, data.user)

        // Load favorites after login
        try {
          const favData = await api.favorites.list()
          useAuthStore.getState().setFavorites(favData.favorites)
        } catch {
          // non-critical
        }
      } catch (err) {
        if (err instanceof Error) {
          if (err.message.includes("401")) {
            setError("Неверное имя пользователя или пароль")
          } else {
            setError("Ошибка соединения с сервером")
          }
        }
      }
      setLoading(false)
    },
    [username, password, setAuth]
  )

  // Show nothing while hydrating (prevents login flash on reload)
  if (!hydrated) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ height: "100dvh", background: "var(--bg-primary)" }}
      />
    )
  }

  // Not authenticated — show full-screen login
  if (!token) {
    return (
      <div
        className="flex flex-col items-center justify-center px-6"
        style={{
          height: "100dvh",
          background: "var(--bg-primary)",
          fontFamily: "var(--font-sans)",
        }}
      >
        <div className="w-full max-w-sm">
          <h1
            className="text-xl font-semibold mb-1 text-center"
            style={{ color: "var(--text-primary)" }}
          >
            Справочник ЭИМ
          </h1>
          <p
            className="text-sm mb-8 text-center"
            style={{ color: "var(--text-muted)" }}
          >
            Войдите для доступа
          </p>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label
                htmlFor="gate-username"
                className="block text-xs font-medium mb-1"
                style={{ color: "var(--text-secondary)" }}
              >
                Имя пользователя
              </label>
              <input
                id="gate-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
                minLength={2}
                className="w-full rounded-lg border px-3 py-2.5 text-sm"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-secondary)",
                  color: "var(--text-primary)",
                }}
              />
            </div>

            <div>
              <label
                htmlFor="gate-password"
                className="block text-xs font-medium mb-1"
                style={{ color: "var(--text-secondary)" }}
              >
                Пароль
              </label>
              <input
                id="gate-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                minLength={4}
                className="w-full rounded-lg border px-3 py-2.5 text-sm"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-secondary)",
                  color: "var(--text-primary)",
                }}
              />
            </div>

            {error && (
              <p className="text-xs px-1" style={{ color: "#dc2626" }}>
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-medium transition-opacity disabled:opacity-50"
              style={{ background: "var(--accent-warm)", color: "#fff" }}
            >
              <LogIn size={16} strokeWidth={1.25} />
              {loading ? "Загрузка..." : "Войти"}
            </button>
          </form>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
