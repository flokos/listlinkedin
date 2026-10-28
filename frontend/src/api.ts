// Typed client for the Django API (/api/v1/). Shapes follow backend/apps/sharing/serializers.py.

export interface SharedList {
  id: string
  public_code: string
  public_url: string
  title: string
  created_at: string
  expires_at: string
}

export interface SharedLink {
  id: string
  title: string | null
  destination_url: string
  short_url: string | null
  created_at: string
  updated_at: string
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...init.headers },
  })
  const body: unknown = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, body)
  return body as T
}

const code = (listCode: string) => encodeURIComponent(listCode)

export const getList = (listCode: string) => request<SharedList>(`/lists/${code(listCode)}/`)

export const getLinks = (listCode: string, page = 1) =>
  request<Page<SharedLink>>(`/lists/${code(listCode)}/links/?page=${page}`)
