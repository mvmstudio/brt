"use client"

import { useEffect, useCallback } from "react"
import { useReaderStore } from "@/stores/reader"
import { PageView } from "@/components/reader/PageView"
import { TopBar } from "@/components/reader/TopBar"
import { BottomNav } from "@/components/reader/BottomNav"
import { TocSidebar } from "@/components/reader/TocSidebar"
import PullToRefresh from "@/components/ui/PullToRefresh"

export default function ReaderPage() {
  const { currentPage, setPage, loadToc, loadBookmarks, theme } = useReaderStore()

  useEffect(() => {
    loadToc()
    loadBookmarks()
    setPage(currentPage)
  }, [])

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
  }, [theme])

  const handleRefresh = useCallback(async () => {
    await Promise.all([
      loadToc(),
      loadBookmarks(),
      setPage(currentPage),
    ])
  }, [currentPage, loadToc, loadBookmarks, setPage])

  return (
    <div id="reader-root" className="flex flex-col h-dvh">
      <TopBar />
      <PullToRefresh onRefresh={handleRefresh} className="flex-1 overflow-y-auto">
        <PageView />
      </PullToRefresh>
      <BottomNav />
      <TocSidebar />
    </div>
  )
}
