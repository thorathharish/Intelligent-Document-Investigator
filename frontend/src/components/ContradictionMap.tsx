import { Fragment } from 'react'
import type { Aspect, Claim } from '../api/types'
import { conflictHeadline, displayName, locationOf, plural } from '../lib/format'

interface Props {
  aspect: Aspect
  claims: Map<string, Claim>
  selectedClaimId: string | null
  onSelectClaim: (claimId: string) => void
}

/** Competing verified positions for the selected question. Nothing here ranks one side above another. */
export function ContradictionMap({ aspect, claims, selectedClaimId, onSelectClaim }: Props) {
  return (
    <div data-testid="conflict" className="rounded-lg border border-red-200 bg-red-50/50 p-3">
      <p className="font-serif text-lg leading-snug text-red-900">{conflictHeadline(aspect.label)}</p>
      <div className="mt-2.5 flex flex-col">
        {aspect.positions.map((position, i) => (
          <Fragment key={position.key}>
            {i > 0 && (
              <div className="py-1 text-center font-serif text-2xl font-semibold leading-none text-red-700" aria-label="conflicts with">
                ≠
              </div>
            )}
            <div data-testid="position" className="rounded-lg border-2 border-red-200 bg-white p-3">
              <div className="flex items-baseline justify-between gap-2">
                <p className="font-serif text-3xl leading-none">{position.display}</p>
                <p className="text-xs font-medium text-ink-soft">{plural(position.document_ids.length, 'document')}</p>
              </div>
              <ul className="mt-2.5 space-y-1.5">
                {position.claim_ids.map((claimId) => {
                  const claim = claims.get(claimId)
                  if (!claim) return null
                  const active = selectedClaimId === claimId
                  return (
                    <li key={claimId}>
                      <button
                        type="button"
                        data-testid="position-source"
                        title="Show this passage in the evidence above"
                        onClick={() => onSelectClaim(claimId)}
                        className={`w-full rounded-md border px-2.5 py-1.5 text-left transition-colors ${
                          active ? 'border-ink bg-ink text-white' : 'border-line bg-paper hover:border-accent'
                        }`}
                      >
                        <span className="block text-sm font-medium leading-snug">
                          {displayName(claim.evidence.document)}
                        </span>
                        <span className={`text-xs ${active ? 'text-slate-200' : 'text-ink-soft'}`}>
                          {locationOf(claim.evidence)}
                          {claim.evidence.extraction_method === 'ocr' && ' · scanned'}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          </Fragment>
        ))}
      </div>

      {aspect.notes.map((note, i) => (
        <p key={i} data-testid="supersession-note" className="mt-2.5 rounded-md bg-white p-2.5 text-sm">
          <span className="font-semibold">Possible supersession signal.</span>{' '}
          {displayName(note.evidence.document)} says it replaces or amends an earlier provision:{' '}
          <span className="verified-quote">{note.evidence.quote}</span>{' '}
          <span className="text-xs text-ink-soft">({locationOf(note.evidence)})</span>
        </p>
      ))}
      <p className="mt-2.5 text-xs font-medium text-red-900">
        Both positions are shown with their sources. No side has been chosen for you.
      </p>
    </div>
  )
}
