import type { ApiError } from './types'

// Thin fetch wrapper: returns parsed JSON, throws {code, message} on a non-2xx response.
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
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
