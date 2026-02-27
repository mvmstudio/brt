const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {}
  try {
    const raw = localStorage.getItem("brt-auth")
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    const token = parsed?.state?.token
    if (token) return { Authorization: `Bearer ${token}` }
  } catch {
    // ignore
  }
  return {}
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export interface TocEntry {
  id: number
  level: number
  title: string
  page_num: number
  parent_id: number | null
  sort_order: number
}

export interface Page {
  page_num: number
  title: string | null
  chapter: string | null
  render_mode: "html" | "image"
  html_content: string
  plain_text: string
  has_tables: boolean
  has_images: boolean
  total_pages: number
}

export interface SearchResult {
  page_num: number
  title: string | null
  chapter: string | null
  snippet: string
}

export interface Bookmark {
  id: number
  page_num: number
  title: string | null
  created_at: string
}

// ─── Handbook types ────────────────────────────

export interface HandbookStats {
  conditions: number
  remedies: number
  symptoms: number
  nosodes: number
  etiology: number
  organs: number
  total: number
}

export interface HandbookSearchResult {
  type: string
  name: string
  snippet: string
  entity_id: number
  rank: number
}

export interface Condition {
  id: number
  condition_name: string
  remedies: string[]
  source_page: number | null
  description: string | null
  content_source: string | null
}

export interface ConditionDetail extends Condition {
  remedies_details: {
    id: number | null
    name_lat: string
    name_rus: string | null
    summary: string | null
  }[]
}

export interface Remedy {
  id: number
  name_lat: string
  name_rus: string | null
  summary: string | null
  content_source?: string | null
}

export interface RemedySymptom {
  system: string
  system_name: string
  description: string
}

export interface RemedyDetail extends Remedy {
  source_pages: number[]
  symptoms: RemedySymptom[]
  related_conditions: { id: number; condition_name: string }[]
}

export interface Nosode {
  id: number
  number: number | null
  name_lat: string
  name_rus: string | null
  category: string | null
  source_page: number | null
  description: string | null
  content_source: string | null
  remedies_list: string[] | null
}

export interface EtiologyEntry {
  id: number
  disease_system: string
  agent_type: string
  agent_name: string
  agent_name_rus: string | null
  source_page: number | null
  description: string | null
  content_source: string | null
  remedies_list: string[] | null
}

export interface OrganPrep {
  id: number
  disease_category: string | null
  organ_name: string
  organ_name_lat: string | null
  manufacturer: string | null
  source_page: number | null
  description: string | null
  content_source: string | null
  remedies_list: string[] | null
}

// ─── Auth types ────────────────────────────────

export interface AuthUser {
  id: number
  username: string
}

export interface AuthResponse {
  token: string
  user: AuthUser
}

export interface FavoriteItem {
  id: number
  entity_type: string
  entity_id: number
  entity_name?: string
  created_at: string
}

export const api = {
  getToc: () => fetchAPI<TocEntry[]>("/api/toc"),

  getPage: (pageNum: number) => fetchAPI<Page>(`/api/pages/${pageNum}`),

  getPageImageUrl: (pageNum: number) =>
    `${API_BASE}/static/images/page_${String(pageNum).padStart(4, "0")}.png`,

  search: (query: string, limit = 20) =>
    fetchAPI<{ results: SearchResult[]; total: number }>("/api/search", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    }),

  getBookmarks: () => fetchAPI<Bookmark[]>("/api/bookmarks"),

  addBookmark: (page_num: number, title?: string) =>
    fetchAPI("/api/bookmarks", {
      method: "POST",
      body: JSON.stringify({ page_num, title }),
    }),

  removeBookmark: (page_num: number) =>
    fetchAPI(`/api/bookmarks/${page_num}`, { method: "DELETE" }),

  // ─── Auth ──────────────────────────────────────

  auth: {
    register: (username: string, password: string) =>
      fetchAPI<AuthResponse>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),

    login: (username: string, password: string) =>
      fetchAPI<AuthResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),

    me: () => fetchAPI<AuthUser>("/api/auth/me"),
  },

  // ─── Favorites ─────────────────────────────────

  favorites: {
    list: (entityType?: string, enriched?: boolean) => {
      const params = new URLSearchParams()
      if (entityType) params.set("entity_type", entityType)
      if (enriched) params.set("enriched", "true")
      const qs = params.toString()
      return fetchAPI<{ favorites: FavoriteItem[] }>(
        `/api/favorites${qs ? `?${qs}` : ""}`
      )
    },

    add: (entity_type: string, entity_id: number) =>
      fetchAPI<{ status: string }>("/api/favorites", {
        method: "POST",
        body: JSON.stringify({ entity_type, entity_id }),
      }),

    remove: (entity_type: string, entity_id: number) =>
      fetchAPI<{ status: string }>("/api/favorites", {
        method: "DELETE",
        body: JSON.stringify({ entity_type, entity_id }),
      }),
  },

  // ─── Handbook ────────────────────────────────

  handbook: {
    stats: () => fetchAPI<HandbookStats>("/api/handbook/stats"),

    search: (q: string, limit = 20) =>
      fetchAPI<{ results: HandbookSearchResult[]; total: number }>(
        `/api/handbook/search?q=${encodeURIComponent(q)}&limit=${limit}`
      ),

    conditions: (limit = 200, offset = 0) =>
      fetchAPI<{ results: Condition[]; total: number }>(
        `/api/handbook/conditions?limit=${limit}&offset=${offset}`
      ),

    condition: (id: number) => fetchAPI<ConditionDetail>(`/api/handbook/conditions/${id}`),

    remedies: (limit = 600, offset = 0) =>
      fetchAPI<{ results: Remedy[]; total: number }>(
        `/api/handbook/remedies?limit=${limit}&offset=${offset}`
      ),

    remedy: (id: number) => fetchAPI<RemedyDetail>(`/api/handbook/remedies/${id}`),

    nosodes: (category?: string, limit = 200) => {
      const params = new URLSearchParams({ limit: String(limit) })
      if (category) params.set("category", category)
      return fetchAPI<{ results: Nosode[]; total: number; categories: string[] }>(
        `/api/handbook/nosodes?${params}`
      )
    },

    etiology: (diseaseSystem?: string, agentType?: string, limit = 300) => {
      const params = new URLSearchParams({ limit: String(limit) })
      if (diseaseSystem) params.set("disease_system", diseaseSystem)
      if (agentType) params.set("agent_type", agentType)
      return fetchAPI<{
        results: EtiologyEntry[]
        total: number
        disease_systems: string[]
        agent_types: string[]
      }>(`/api/handbook/etiology?${params}`)
    },

    organs: (category?: string, limit = 200) => {
      const params = new URLSearchParams({ limit: String(limit) })
      if (category) params.set("category", category)
      return fetchAPI<{ results: OrganPrep[]; total: number; categories: string[] }>(
        `/api/handbook/organs?${params}`
      )
    },
  },
}
