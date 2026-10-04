import type { RunResult } from '../api/types'

// Presentation only. A result that comes back from the run cache or from a recording returns in
// milliseconds; this holds it behind the loading state for a short, random time. Results from a
// live model call are never delayed, and nothing here touches the backend or the cache.
// Set VITE_DEMO_DELAY_MAX_MS=0 to switch the delay off.
const MIN_MS = Number(import.meta.env.VITE_DEMO_DELAY_MIN_MS ?? 5000)
const MAX_MS = Number(import.meta.env.VITE_DEMO_DELAY_MAX_MS ?? 20000)

export function isReplayed(run: RunResult): boolean {
  return run.cached || run.signals.llm_source === 'recording'
}

export function presentationDelayMs(run: RunResult): number {
  if (!isReplayed(run) || !(MAX_MS > 0)) return 0
  const low = Math.max(0, Math.min(MIN_MS, MAX_MS))
  return Math.round(low + Math.random() * (MAX_MS - low))
}
