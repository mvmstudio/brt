"use client"

import { useEffect } from "react"
import { useReaderStore } from "@/stores/reader"
import { PageView } from "@/components/reader/PageView"
import { TopBar } from "@/components/reader/TopBar"
import { BottomNav } from "@/components/reader/BottomNav"
import { TocSidebar } from "@/components/reader/TocSidebar"

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

  return (
    <div id="reader-root" className="flex flex-col h-dvh">
      <TopBar />
      <main className="flex-1 overflow-y-auto">
        <PageView />
      </main>
      <BottomNav />
      <TocSidebar />
    </div>
  )
}
