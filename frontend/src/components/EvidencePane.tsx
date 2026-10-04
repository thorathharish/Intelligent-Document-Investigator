import { useEffect, useRef } from 'react'
import type { Evidence, RunResult } from '../api/types'

function location(evidence: Evidence): string {
  const parts = []
  if (evidence.page != null) parts.push(`Page ${evidence.page}`)
  if (evidence.section) parts.push(evidence.section)
  if (parts.length === 0) parts.push(`Paragraph ${evidence.paragraph}`)
  return parts.join(' · ')
}

function EvidenceCard({ evidence, number, active }: { evidence: Evidence; number?: number; active?: boolean }) {
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [active])

  return (
    <li
      ref={ref}
      data-testid="evidence-card"
      className={`rounded border bg-white p-3 text-sm ${active ? 'border-slate-900 ring-1 ring-slate-900' : 'border-slate-200'}`}
    >
      <div className="flex items-start gap-2">
        {number != null && (
          <span className="rounded bg-blue-100 px-1.5 text-xs font-semibold text-blue-900">{number}</span>
        )}
        <div className="min-w-0">
          <div className="break-all font-medium" data-testid="evidence-document">
            {evidence.document}
          </div>
          <div className="text-xs text-slate-500" data-testid="evidence-location">
            {location(evidence)}
            {evidence.extraction_method === 'ocr' && ' · scanned image'}
            {evidence.ocr_quality === 'low' && ' (low quality)'}
          </div>
        </div>
      </div>
      <blockquote
        data-testid="evidence-quote"
        className="mt-2 border-l-4 border-amber-300 bg-amber-50 px-2 py-1 text-slate-800"
      >
        “{evidence.quote}”
      </blockquote>
    </li>
  )
}

export function EvidencePane({ run, selectedClaimId }: { run: RunResult | null; selectedClaimId: string | null }) {
  return (
    <section className="flex h-full flex-col">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Evidence</h2>
      {!run && <p className="mt-2 text-sm text-slate-500">Ask a question to see its supporting passages.</p>}
      {run && (
        <div className="mt-2 flex-1 overflow-y-auto">
          {run.claims.length > 0 && (
            <ul className="space-y-2">
              {run.claims.map((claim) => (
                <EvidenceCard
                  key={claim.id}
                  evidence={claim.evidence}
                  number={claim.citation}
                  active={claim.id === selectedClaimId}
                />
              ))}
            </ul>
          )}
          {run.claims.length === 0 && run.related.length > 0 && (
            <>
              <p className="mb-2 text-xs text-slate-500">Related passages. They do not answer the question.</p>
              <ul className="space-y-2">
                {run.related.map((evidence) => (
                  <EvidenceCard key={evidence.chunk_id} evidence={evidence} />
                ))}
              </ul>
            </>
          )}
          {run.claims.length === 0 && run.related.length === 0 && (
            <p className="text-sm text-slate-500">No supporting passages.</p>
          )}
        </div>
      )}
    </section>
  )
}
