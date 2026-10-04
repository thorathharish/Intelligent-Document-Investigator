import type { ApiError } from './types'

// Where the API lives. Empty in local development, where the dev server proxies /api to the backend;
// set VITE_API_BASE_URL to the backend's public URL when the frontend is hosted separately.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

export function apiUrl(path: string): string {
  return `${API_BASE}/api${path}`
}

// Thin fetch wrapper: returns parsed JSON, throws {code, message} on a non-2xx response.
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), init)
  } catch {
    throw { code: 'network', message: 'The server could not be reached. Please try again in a moment.' } as ApiError
  }
  if (!response.ok) {
    let error: ApiError = { code: 'error', message: `Request failed (${response.status})` }
    try {
      const body = await response.json()
      if (body?.error?.message) error = body.error
    } catch {
      // keep the generic error
    }
    throw error
  }
  return response.json() as Promise<T>
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
