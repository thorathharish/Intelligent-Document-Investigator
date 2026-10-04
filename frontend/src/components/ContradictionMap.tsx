import { Fragment } from 'react'
import type { Aspect, Claim } from '../api/types'
import { locationOf, plural } from '../lib/format'

interface Props {
  aspect: Aspect
  claims: Map<string, Claim>
  selectedClaimId: string | null
  onSelectClaim: (claimId: string) => void
}

/** Competing verified positions side by side. Nothing here ranks one side above another. */
export function ContradictionMap({ aspect, claims, selectedClaimId, onSelectClaim }: Props) {
  return (
    <div data-testid="conflict" className="mt-4 rounded-lg border border-red-200 bg-red-50/60 p-4">
      <p className="text-sm font-semibold text-red-900">Evidence disagrees on {aspect.label.toLowerCase()}</p>
      <div className="mt-3 flex flex-wrap items-stretch gap-2">
        {aspect.positions.map((position, i) => (
          <Fragment key={position.key}>
            {i > 0 && (
              <div className="flex items-center px-1 font-serif text-2xl text-red-800" aria-label="conflicts with">
                ≠
              </div>
            )}
            <div data-testid="position" className="min-w-[200px] flex-1 rounded-md border border-line bg-white p-3">
              <p className="font-serif text-2xl leading-tight">{position.display}</p>
              <p className="text-xs text-ink-soft">{plural(position.document_ids.length, 'document')}</p>
              <ul className="mt-2 space-y-1.5">
                {position.claim_ids.map((claimId) => {
                  const claim = claims.get(claimId)
                  if (!claim) return null
                  const active = selectedClaimId === claimId
                  return (
                    <li key={claimId}>
                      <button
                        type="button"
                        data-testid="position-source"
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectClaim(claimId)
                        }}
                        className={`w-full rounded border px-2 py-1.5 text-left text-xs transition-colors ${
                          active ? 'border-ink bg-ink text-white' : 'border-line bg-paper hover:border-accent'
                        }`}
                      >
                        <span className="block truncate font-medium">{claim.evidence.document}</span>
                        <span className={active ? 'text-slate-200' : 'text-ink-soft'}>
                          {locationOf(claim.evidence)}
                          {claim.evidence.extraction_method === 'ocr' && ', scanned'}
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
        <p key={i} data-testid="supersession-note" className="mt-3 text-xs text-slate-700">
          <span className="font-semibold">Possible supersession signal.</span> {note.text}{' '}
          <span className="verified-quote">{note.evidence.quote}</span> ({locationOf(note.evidence)})
        </p>
      ))}
      <p className="mt-3 text-xs text-red-900">
        Both positions are shown with their sources. No side has been chosen for you.
      </p>
    </div>
  )
}
