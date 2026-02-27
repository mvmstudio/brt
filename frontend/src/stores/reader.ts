import { create } from "zustand"
import { persist } from "zustand/middleware"
import { api, type Page, type TocEntry, type Bookmark } from "@/lib/api"

interface ReaderState {
  currentPage: number
  totalPages: number
  pageData: Page | null
  toc: TocEntry[]
  bookmarks: Set<number>
  theme: "light" | "dark" | "sepia"
  tocOpen: boolean
  loading: boolean

  setPage: (page: number) => Promise<void>
  nextPage: () => void
  prevPage: () => void
  loadToc: () => Promise<void>
  loadBookmarks: () => Promise<void>
  toggleBookmark: (page: number, title?: string) => Promise<void>
  setTheme: (theme: "light" | "dark" | "sepia") => void
  setTocOpen: (open: boolean) => void
}

export const useReaderStore = create<ReaderState>()(
  persist(
    (set, get) => ({
      currentPage: 1,
      totalPages: 482,
      pageData: null,
      toc: [],
      bookmarks: new Set<number>(),
      theme: "light",
      tocOpen: false,
      loading: false,

      setPage: async (page: number) => {
        const { totalPages } = get()
        const clampedPage = Math.max(1, Math.min(page, totalPages))
        set({ loading: true, currentPage: clampedPage })
        try {
          const data = await api.getPage(clampedPage)
          set({ pageData: data, totalPages: data.total_pages, loading: false })
        } catch {
          set({ loading: false })
        }
      },

      nextPage: () => {
        const { currentPage, totalPages, setPage } = get()
        if (currentPage < totalPages) setPage(currentPage + 1)
      },

      prevPage: () => {
        const { currentPage, setPage } = get()
        if (currentPage > 1) setPage(currentPage - 1)
      },

      loadToc: async () => {
        try {
          const toc = await api.getToc()
          set({ toc })
        } catch {
          // silent
        }
      },

      loadBookmarks: async () => {
        try {
          const bms = await api.getBookmarks()
          set({ bookmarks: new Set(bms.map((b: Bookmark) => b.page_num)) })
        } catch {
          // silent
        }
      },

      toggleBookmark: async (page: number, title?: string) => {
        const { bookmarks } = get()
        if (bookmarks.has(page)) {
          await api.removeBookmark(page)
          bookmarks.delete(page)
        } else {
          await api.addBookmark(page, title)
          bookmarks.add(page)
        }
        set({ bookmarks: new Set(bookmarks) })
      },

      setTheme: (theme) => set({ theme }),
      setTocOpen: (tocOpen) => set({ tocOpen }),
    }),
    {
      name: "brt-reader",
      partialize: (state) => ({
        currentPage: state.currentPage,
        theme: state.theme,
      }),
    }
  )
)
