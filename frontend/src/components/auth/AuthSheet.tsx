"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import { X, LogIn, UserPlus } from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore } from "@/stores/auth"

interface AuthSheetProps {
  open: boolean
  onClose: () => void
}

export function AuthSheet({ open, onClose }: AuthSheetProps) {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore((s) => s.setAuth)
  const sheetRef = useRef<HTMLDivElement>(null)

  // Reset form on open
  useEffect(() => {
    if (open) {
      setUsername("")
      setPassword("")
      setError(null)
      setLoading(false)
    }
  }, [open])

  // Close on backdrop click
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (sheetRef.current && !sheetRef.current.contains(e.target as Node)) {
        onClose()
      }
    },
    [onClose]
  )

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const fn = mode === "login" ? api.auth.login : api.auth.register
      const data = await fn(username, password)
      setAuth(data.token, data.user)

      // Load favorites after login
      try {
        const favData = await api.favorites.list()
        useAuthStore.getState().setFavorites(favData.favorites)
      } catch {
        // non-critical
      }

      onClose()
    } catch (err) {
      if (err instanceof Error) {
        if (err.message.includes("409")) {
          setError("Имя пользователя уже занято")
        } else if (err.message.includes("401")) {
          setError("Неверное имя пользователя или пароль")
        } else {
          setError("Ошибка соединения с сервером")
        }
      }
    }
    setLoading(false)
  }

  if (!open) return null

  return (
    <div
      id="auth-backdrop"
      className="fixed inset-0 z-50"
      style={{ background: "rgba(0,0,0,0.4)" }}
      onClick={handleBackdropClick}
    >
      <div
        ref={sheetRef}
        id="auth-sheet"
        className="fixed bottom-0 left-0 right-0 mx-auto max-w-md rounded-t-2xl px-5 pt-3 animate-slide-up"
        style={{
          background: "var(--bg-primary)",
          fontFamily: "var(--font-sans)",
          paddingBottom: "max(2rem, env(safe-area-inset-bottom))",
        }}
      >
        {/* Handle bar */}
        <div className="flex justify-center mb-3">
          <div
            className="w-10 h-1 rounded-full"
            style={{ background: "var(--border)" }}
          />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            {mode === "login" ? "Вход" : "Регистрация"}
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
          >
            <X size={20} strokeWidth={1.25} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label
              htmlFor="auth-username"
              className="block text-xs font-medium mb-1"
              style={{ color: "var(--text-secondary)" }}
            >
              Имя пользователя
            </label>
            <input
              id="auth-username"
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
              htmlFor="auth-password"
              className="block text-xs font-medium mb-1"
              style={{ color: "var(--text-secondary)" }}
            >
              Пароль
            </label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
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
            {mode === "login" ? (
              <LogIn size={16} strokeWidth={1.25} />
            ) : (
              <UserPlus size={16} strokeWidth={1.25} />
            )}
            {loading
              ? "Загрузка..."
              : mode === "login"
                ? "Войти"
                : "Зарегистрироваться"}
          </button>
        </form>

        {/* Toggle mode */}
        <p className="text-center text-xs mt-4" style={{ color: "var(--text-muted)" }}>
          {mode === "login" ? "Нет аккаунта?" : "Уже есть аккаунт?"}{" "}
          <button
            onClick={() => {
              setMode(mode === "login" ? "register" : "login")
              setError(null)
            }}
            className="font-medium underline"
            style={{ color: "var(--accent-warm)" }}
          >
            {mode === "login" ? "Регистрация" : "Войти"}
          </button>
        </p>
      </div>
    </div>
  )
}
