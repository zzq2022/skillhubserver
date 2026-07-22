/**
 * SkillHub API client for /api/v1 (session cookie + CSRF double-submit).
 */

export type ApiErrorBody = {
  error: { code: string; message: string }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

let csrfToken: string | null = null

export function getCsrfToken(): string | null {
  return csrfToken
}

export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export type RequestOptions = {
  method?: string
  body?: unknown
  /** When true, send multipart FormData body (do not JSON-stringify). */
  formData?: FormData
  /** When true, return raw Response (for ZIP / binary). */
  raw?: boolean
  headers?: Record<string, string>
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const data = (await res.json()) as ApiErrorBody
    if (data?.error?.code) {
      return new ApiError(res.status, data.error.code, data.error.message)
    }
  } catch {
    /* ignore */
  }
  return new ApiError(res.status, 'http_error', res.statusText || 'Request failed')
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = (options.method || 'GET').toUpperCase()
  const headers: Record<string, string> = {
    ...(options.headers || {}),
  }

  if (WRITE_METHODS.has(method) && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const res = await fetch(`/api/v1${path}`, {
    method,
    credentials: 'include',
    headers,
    body,
  })

  if (options.raw) {
    if (!res.ok) {
      throw await parseError(res)
    }
    return res as unknown as T
  }

  if (!res.ok) {
    throw await parseError(res)
  }

  if (res.status === 204) {
    return undefined as T
  }

  const json = (await res.json()) as { data?: T } & T
  if (json && typeof json === 'object' && 'data' in json) {
    return json as T
  }
  return json as T
}

/** Typed helpers that unwrap `{ data }` envelope. */
export async function apiData<T>(path: string, options?: RequestOptions): Promise<T> {
  const payload = await apiRequest<{ data: T }>(path, options)
  return payload.data
}

export async function apiDataList<T>(
  path: string,
  options?: RequestOptions,
): Promise<{ data: T[]; pagination?: { page: number; pageSize: number; total: number } }> {
  return apiRequest(path, options)
}
