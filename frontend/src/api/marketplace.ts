/**
 * Marketplace API — AgentWork-compatible /api/skillhub/* (session cookie OK).
 */

import { ApiError, getCsrfToken } from './client'

export type SkillSortType =
  | 'trending'
  | 'top'
  | 'new'
  | 'most_starred'
  | 'featured'

export type SkillPublicSummary = {
  id: string
  name: string
  description?: string
  slug?: string
  registrySlug?: string
  authorName?: string
  authorUsername?: string
  category?: string
  starCount?: number
  downloadCount?: number
  viewCount?: number
  isStarred?: boolean
  featured?: boolean
  updatedAt?: string
}

export type SkillDetail = SkillPublicSummary & {
  skillMd?: string | null
  skillMdAvailable?: boolean
  visibility?: string
  approvalStatus?: string | null
  ownerUserId?: string
}

export type SkillStats = {
  totalSkills: number
  totalStars: number
  totalDownloads: number
}

export type PaginatedResult<T> = {
  items: T[]
  total: number
  page: number
  pageSize: number
  startIndex: number
  endIndex: number
}

const WRITE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

async function marketplaceRequest<T>(
  path: string,
  options: { method?: string; body?: unknown; raw?: boolean } = {},
): Promise<T> {
  const method = (options.method || 'GET').toUpperCase()
  const headers: Record<string, string> = {}
  if (WRITE.has(method)) {
    const csrf = getCsrfToken()
    if (csrf) headers['X-CSRF-Token'] = csrf
  }
  let body: BodyInit | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  const res = await fetch(`/api/skillhub${path}`, {
    method,
    credentials: 'include',
    headers,
    body,
  })
  if (options.raw) {
    if (!res.ok) {
      let msg = res.statusText
      try {
        const j = await res.json()
        msg = j?.error?.message || msg
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, 'http_error', msg)
    }
    return res as unknown as T
  }
  if (!res.ok) {
    let code = 'http_error'
    let message = res.statusText
    try {
      const j = await res.json()
      if (j?.error) {
        code = j.error.code || code
        message = j.error.message || message
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, code, message)
  }
  if (res.status === 204) return undefined as T
  const json = await res.json()
  if (json && typeof json === 'object' && 'data' in json) {
    return json.data as T
  }
  return json as T
}

export async function fetchPublicSkills(
  page = 1,
  sort: SkillSortType = 'new',
  category?: string,
  limit = 20,
): Promise<PaginatedResult<SkillPublicSummary>> {
  const params = new URLSearchParams({ page: String(page), sort, limit: String(limit) })
  if (category && category !== 'all') params.set('category', category)
  return marketplaceRequest(`/public?${params}`)
}

export async function searchPublicSkills(
  q: string,
  page = 1,
  sort: SkillSortType = 'new',
  category?: string,
  limit = 20,
): Promise<PaginatedResult<SkillPublicSummary>> {
  const params = new URLSearchParams({
    q,
    page: String(page),
    sort,
    limit: String(limit),
  })
  if (category && category !== 'all') params.set('category', category)
  return marketplaceRequest(`/public/search?${params}`)
}

export async function fetchMarketplaceStats(): Promise<SkillStats> {
  return marketplaceRequest('/public/stats')
}

export async function fetchFeaturedSkills(limit = 6): Promise<SkillPublicSummary[]> {
  return marketplaceRequest(`/public/featured?limit=${limit}`)
}

export async function fetchPublicSkillDetail(id: string): Promise<SkillDetail> {
  return marketplaceRequest(`/public/${encodeURIComponent(id)}`)
}

export async function toggleSkillStar(id: string): Promise<{ starred: boolean }> {
  return marketplaceRequest(`/public/${encodeURIComponent(id)}/star`, {
    method: 'POST',
  })
}

export async function reportSkillView(id: string): Promise<void> {
  await marketplaceRequest(`/public/${encodeURIComponent(id)}/view`, {
    method: 'POST',
  })
}

export async function downloadSkillZip(id: string): Promise<Blob> {
  const res = await marketplaceRequest<Response>(
    `/${encodeURIComponent(id)}/download`,
    { raw: true },
  )
  return res.blob()
}
