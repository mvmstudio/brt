"use client"

import { useState, useEffect, useCallback } from "react"
import { ArrowLeft, User, LogOut, Search, Stethoscope, Pill, Bug, Microscope, Heart } from "lucide-react"
import Link from "next/link"
import { useReaderStore } from "@/stores/reader"
import { useAuthStore } from "@/stores/auth"
import { api } from "@/lib/api"
import { AuthSheet } from "@/components/auth/AuthSheet"
import { HandbookSearch } from "@/components/handbook/HandbookSearch"
import { ConditionsTab } from "@/components/handbook/ConditionsTab"
import { RemediesTab } from "@/components/handbook/RemediesTab"
import { NosodesTab } from "@/components/handbook/NosodesTab"
import { EtiologyTab } from "@/components/handbook/EtiologyTab"
import { OrgansTab } from "@/components/handbook/OrgansTab"

const TABS = [
  { id: "search", label: "Поиск", icon: Search },
  { id: "conditions", label: "Болезни", icon: Stethoscope },
  { id: "remedies", label: "Препараты", icon: Pill },
  { id: "nosodes", label: "Нозоды", icon: Bug },
  { id: "etiology", label: "Этиология", icon: Microscope },
  { id: "organs", label: "Органы", icon: Heart },
] as const

type TabId = (typeof TABS)[number]["id"]

const TYPE_TO_TAB: Record<string, TabId> = {
  condition: "conditions",
  remedy: "remedies",
  nosode: "nosodes",
  etiology: "etiology",
  organ: "organs",
}

export default function HandbookPage() {
  const [activeTab, setActiveTab] = useState<TabId>("conditions")
  const [highlightedId, setHighlightedId] = useState<number | null>(null)
  const [authOpen, setAuthOpen] = useState(false)
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const { theme } = useReaderStore()
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.token)
  const logout = useAuthStore((s) => s.logout)

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
  }, [theme])

  // Load favorites on mount if authenticated
  useEffect(() => {
    if (token) {
      api.favorites.list().then((data) => {
        useAuthStore.getState().setFavorites(data.favorites)
      }).catch(() => {})
    }
  }, [token])

  const handleSearchNavigate = useCallback((type: string, entityId: number) => {
    const tab = TYPE_TO_TAB[type]
    if (!tab) return
    setHighlightedId(entityId)
    setActiveTab(tab)
  }, [])

  const handleTabClick = useCallback((tabId: TabId) => {
    setHighlightedId(null)
    setActiveTab(tabId)
  }, [])

  const handleAuthRequired = useCallback(() => {
    setAuthOpen(true)
  }, [])

  const handleFavoritesToggle = useCallback(() => {
    if (!token) {
      setAuthOpen(true)
      return
    }
    setShowFavoritesOnly((v) => !v)
  }, [token])

  return (
    <div id="handbook-root" className="flex flex-col h-dvh" style={{ background: "var(--bg-primary)" }}>
      {/* Header */}
      <header
        id="handbook-header"
        className="shrink-0 px-4 py-3 border-b"
        style={{
          background: "var(--bg-secondary)",
          borderColor: "var(--border-subtle)",
          fontFamily: "var(--font-sans)",
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Link href="/" className="p-2 rounded hover:opacity-70 shrink-0">
            <ArrowLeft size={20} strokeWidth={1.25} />
          </Link>
          <h1 className="flex-1 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            Справочник
          </h1>

          {/* Favorites toggle */}
          {activeTab !== "search" && (
            <button
              onClick={handleFavoritesToggle}
              className="shrink-0 px-3 py-2 rounded-lg text-xs font-medium"
              style={{
                background: showFavoritesOnly ? "var(--accent-warm)" : "transparent",
                color: showFavoritesOnly ? "#fff" : "var(--text-muted)",
                border: showFavoritesOnly ? "none" : "1px solid var(--border)",
              }}
            >
              {showFavoritesOnly ? "Избранное" : "Избранное"}
            </button>
          )}

          {/* Auth button */}
          {user ? (
            <button
              onClick={logout}
              className="shrink-0 p-2 rounded-lg hover:opacity-70"
              style={{ color: "var(--text-muted)" }}
              title={`${user.username} — выйти`}
            >
              <LogOut size={20} strokeWidth={1.25} />
            </button>
          ) : (
            <button
              onClick={() => setAuthOpen(true)}
              className="shrink-0 p-2 rounded-lg hover:opacity-70"
              style={{ color: "var(--text-muted)" }}
            >
              <User size={20} strokeWidth={1.25} />
            </button>
          )}
        </div>

        {/* Tabs */}
        <nav id="handbook-tabs" className="flex gap-1 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-none">
          {TABS.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab.id)}
                className="shrink-0 flex items-center gap-1.5 px-3 py-2.5 rounded-full text-xs font-medium transition-all duration-200"
                style={{
                  background: isActive ? "var(--accent-warm)" : "transparent",
                  color: isActive ? "#fff" : "var(--text-secondary)",
                  border: isActive ? "none" : "1px solid var(--border)",
                }}
                title={tab.label}
              >
                <Icon size={16} strokeWidth={1.25} />
                <span className="hidden sm:inline">{tab.label}</span>
                {isActive && <span className="sm:hidden">{tab.label}</span>}
              </button>
            )
          })}
        </nav>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">
        {activeTab === "search" && <HandbookSearch onNavigate={handleSearchNavigate} />}
        {activeTab === "conditions" && (
          <ConditionsTab
            initialExpandedId={highlightedId}
            onAuthRequired={handleAuthRequired}
            showFavoritesOnly={showFavoritesOnly}
          />
        )}
        {activeTab === "remedies" && (
          <RemediesTab
            initialExpandedId={highlightedId}
            onAuthRequired={handleAuthRequired}
            showFavoritesOnly={showFavoritesOnly}
          />
        )}
        {activeTab === "nosodes" && (
          <NosodesTab
            initialExpandedId={highlightedId}
            onAuthRequired={handleAuthRequired}
            showFavoritesOnly={showFavoritesOnly}
          />
        )}
        {activeTab === "etiology" && (
          <EtiologyTab
            initialExpandedId={highlightedId}
            onAuthRequired={handleAuthRequired}
            showFavoritesOnly={showFavoritesOnly}
          />
        )}
        {activeTab === "organs" && (
          <OrgansTab
            initialExpandedId={highlightedId}
            onAuthRequired={handleAuthRequired}
            showFavoritesOnly={showFavoritesOnly}
          />
        )}
      </main>

      {/* Auth Bottom Sheet */}
      <AuthSheet open={authOpen} onClose={() => setAuthOpen(false)} />
    </div>
  )
}
