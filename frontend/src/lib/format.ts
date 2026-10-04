import type { Evidence, RunResult } from '../api/types'

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`
}

export function fileType(filename: string): string {
  const ext = filename.includes('.') ? filename.split('.').pop()! : ''
  return ext.toUpperCase()
}

/** "Master_Services_Agreement.pdf" -> "Master Services Agreement". Display only; the stored name is unchanged. */
export function displayName(filename: string): string {
  return filename
    .replace(/\.[^.]+$/, '')
    .replace(/_+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Swap stored file names for their readable form inside a sentence. */
export function withDisplayNames(text: string, filenames: string[]): string {
  return filenames.reduce((out, name) => out.split(name).join(displayName(name)), text)
}

/** "Page 2 · 4.2 Payment Terms" — or the paragraph number when the format has no pages. */
export function locationOf(evidence: Evidence): string {
  const parts: string[] = []
  if (evidence.page != null) parts.push(`Page ${evidence.page}`)
  if (evidence.section) parts.push(evidence.section)
  if (parts.length === 0) parts.push(`Paragraph ${evidence.paragraph}`)
  return parts.join(' · ')
}

export function timeOf(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function hasPageImage(evidence: Evidence): boolean {
  return evidence.page != null && ['PDF', 'PNG', 'JPG', 'JPEG'].includes(fileType(evidence.document))
}

/** Headline for a conflicting topic; falls back when the topic has no label. */
export function conflictHeadline(label: string): string {
  const topic = label.trim()
  return topic ? `Evidence disagrees on ${topic.toLowerCase()}` : 'The documents state different values'
}

export interface Contradiction {
  key: string
  label: string
  runId: string
  question: string
  sides: { display: string; documents: string[] }[]
}

/** Every distinct conflict found so far in this investigation, newest run winning for duplicates. */
export function contradictionsOf(runs: RunResult[]): Contradiction[] {
  const found = new Map<string, Contradiction>()
  for (const run of runs) {
    const documentOf = new Map(run.claims.map((c) => [c.id, c.evidence.document]))
    for (const aspect of run.aspects) {
      if (aspect.status !== 'conflict') continue
      const sides = aspect.positions.map((p) => ({
        display: p.display,
        documents: [...new Set(p.claim_ids.map((id) => documentOf.get(id) ?? ''))].filter(Boolean),
      }))
      const key = aspect.positions
        .map((p) => p.key)
        .sort()
        .join('|')
      found.set(key, { key, label: aspect.label, runId: run.run_id, question: run.question, sides })
    }
  }
  return [...found.values()]
}
