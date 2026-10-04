import { BadgeCheck, FileSearch, ScanLine } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Claim, Evidence, RunResult } from '../api/types'
import { displayName, fileType, hasPageImage, locationOf } from '../lib/format'
import { PageViewer } from './PageViewer'

interface CardProps {
  evidence: Evidence
  number?: number
  stated?: { label: string; value: string | null }
  inferred?: boolean
  active?: boolean
  onSelect?: () => void
  onViewPage: (evidence: Evidence) => void
}

function EvidenceCard({ evidence, number, stated, inferred, active, onSelect, onViewPage }: CardProps) {
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [active])

  return (
    <li
      ref={ref}
      data-testid="evidence-card"
      data-active={active ? 'true' : 'false'}
      onClick={onSelect}
      className={`rounded-lg border bg-white p-3 text-sm transition-colors ${
        active ? 'border-ink ring-2 ring-ink/15' : 'border-line'
      } ${onSelect ? 'cursor-pointer hover:border-accent' : ''}`}
    >
      {/* 1 source, 2 location */}
      <div className="flex items-start gap-2">
        {number != null && (
          <span
            className={`flex h-6 min-w-6 items-center justify-center rounded-md px-1 text-xs font-semibold ${
              active ? 'bg-ink text-white' : 'bg-blue-50 text-accent'
            }`}
          >
            {number}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-snug" data-testid="evidence-document" title={evidence.document}>
            {displayName(evidence.document)}
            <span className="ml-1.5 align-middle text-[11px] font-medium text-ink-soft">{fileType(evidence.document)}</span>
          </p>
          <p className="text-xs text-ink-soft" data-testid="evidence-location">
            {locationOf(evidence)}
          </p>
        </div>
      </div>

      {/* 3 verified quote */}
      <p className="mt-3 text-[15px]">
        <span className="verified-quote" data-testid="evidence-quote">
          {evidence.quote}
        </span>
      </p>

      {/* 4 what the passage states */}
      {stated && (
        <div className="mt-3 border-l-2 border-line pl-2.5" data-testid="evidence-stated">
          <p className="text-xs text-ink-soft">{stated.label}</p>
          {stated.value && (
            <p className="text-sm font-semibold">
              {stated.value}
              {inferred && <span className="font-normal text-ink-soft"> (inferred, not stated directly)</span>}
            </p>
          )}
        </div>
      )}

      {/* 5 action */}
      {(evidence.extraction_method === 'ocr' || hasPageImage(evidence)) && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
          {evidence.extraction_method === 'ocr' ? (
            <span data-testid="evidence-ocr" className="inline-flex items-center gap-1 text-amber-800">
              <ScanLine size={12} aria-hidden />
              Read from a scanned image{evidence.ocr_quality === 'low' && ' (low quality)'}
            </span>
          ) : (
            <span />
          )}
          {hasPageImage(evidence) && (
            <button
              type="button"
              data-testid="view-page"
              onClick={(e) => {
                e.stopPropagation()
                onViewPage(evidence)
              }}
              className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 font-medium text-accent hover:border-accent"
            >
              <FileSearch size={12} aria-hidden /> View page
            </button>
          )}
        </div>
      )}
    </li>
  )
}

// When positions conflict, evidence is grouped by position so each side is read together.
function groupClaims(run: RunResult): { title: string | null; claims: Claim[] }[] {
  if (run.claims.length === 0) return []
  const conflicts = run.aspects.filter((a) => a.status === 'conflict')
  if (conflicts.length === 0) return [{ title: null, claims: run.claims }]

  const byId = new Map(run.claims.map((c) => [c.id, c]))
  const used = new Set<string>()
  const groups: { title: string | null; claims: Claim[] }[] = []
  for (const aspect of conflicts) {
    for (const position of aspect.positions) {
      const claims = position.claim_ids.map((id) => byId.get(id)).filter((c): c is Claim => !!c)
      claims.forEach((c) => used.add(c.id))
      groups.push({ title: aspect.label.trim() ? `${aspect.label}: ${position.display}` : position.display, claims })
    }
  }
  const rest = run.claims.filter((c) => !used.has(c.id))
  if (rest.length > 0) groups.push({ title: 'Other evidence', claims: rest })
  return groups
}

interface Props {
  run: RunResult | null
  selectedClaimId: string | null
  onSelectClaim: (claimId: string) => void
}

export function EvidencePane({ run, selectedClaimId, onSelectClaim }: Props) {
  const [viewing, setViewing] = useState<Evidence | null>(null)
  const groups = run ? groupClaims(run) : []
  const aspectLabel = new Map(run?.aspects.map((a) => [a.id, a.label]) ?? [])

  const stated = (claim: Claim) => {
    const label = aspectLabel.get(claim.aspect_id)?.trim() || (claim.position_key ? 'Stated value' : '')
    if (!label) return undefined
    return { label, value: claim.position_key ? claim.value : null }
  }

  return (
    <section className="flex h-full flex-col">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <BadgeCheck size={16} className="text-emerald-700" aria-hidden />
        Verified evidence
      </h2>
      <p className="mt-0.5 text-xs text-ink-soft">
        {run ? (
          <>
            For <span className="font-medium text-ink">“{run.question}”</span>. Each quote was found in the stored
            document text before it was shown.
          </>
        ) : (
          'Each quote is found in the stored document text before it is shown.'
        )}
      </p>

      <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1">
        {!run && <p className="text-sm text-ink-soft">Ask a question to see the passages behind its answer.</p>}

        {groups.map((group) => (
          <div key={group.title ?? 'all'} className="mb-4" data-testid="evidence-group">
            {group.title && <p className="mb-1.5 text-xs font-semibold text-ink-soft">{group.title}</p>}
            <ul className="space-y-2">
              {group.claims.map((claim) => (
                <EvidenceCard
                  key={claim.id}
                  evidence={claim.evidence}
                  number={claim.citation}
                  stated={stated(claim)}
                  inferred={!claim.explicit}
                  active={claim.id === selectedClaimId}
                  onSelect={() => onSelectClaim(claim.id)}
                  onViewPage={setViewing}
                />
              ))}
            </ul>
          </div>
        ))}

        {run && run.claims.length === 0 && run.related.length > 0 && (
          <div data-testid="related">
            <p className="mb-2 text-xs text-ink-soft">
              {run.degraded
                ? 'The closest passages to your question. They have not been analysed.'
                : 'The closest passages found. None of them answers the question.'}
            </p>
            <ul className="space-y-2">
              {run.related.map((evidence) => (
                <EvidenceCard key={evidence.chunk_id} evidence={evidence} onViewPage={setViewing} />
              ))}
            </ul>
          </div>
        )}

        {run && run.claims.length === 0 && run.related.length === 0 && (
          <p className="text-sm text-ink-soft">There are no passages to show for this question.</p>
        )}
      </div>

      {viewing && <PageViewer evidence={viewing} onClose={() => setViewing(null)} />}
    </section>
  )
}
