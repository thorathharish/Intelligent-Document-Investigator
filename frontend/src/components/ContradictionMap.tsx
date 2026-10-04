import { Fragment } from 'react'
import type { Aspect, Claim } from '../api/types'
import { displayName, locationOf, plural } from '../lib/format'

interface Props {
  aspect: Aspect
  claims: Map<string, Claim>
  selectedClaimId: string | null
  onSelectClaim: (claimId: string) => void
}

/** Competing verified positions side by side. Nothing here ranks one side above another. */
export function ContradictionMap({ aspect, claims, selectedClaimId, onSelectClaim }: Props) {
  return (
    <div data-testid="conflict" className="mt-4">
      <p className="font-serif text-2xl leading-snug text-red-900" data-testid="conflict-headline">
        {aspect.label.trim()
          ? `Evidence disagrees on ${aspect.label.trim().toLowerCase()}`
          : 'The documents state different values'}
      </p>
      <div className="mt-3 flex flex-wrap items-stretch gap-3">
        {aspect.positions.map((position, i) => (
          <Fragment key={position.key}>
            {i > 0 && (
              <div className="flex items-center font-serif text-3xl font-semibold text-red-700" aria-label="conflicts with">
                ≠
              </div>
            )}
            <div
              data-testid="position"
              className="min-w-[210px] flex-1 rounded-lg border-2 border-red-200 bg-white p-4"
            >
              <div className="flex items-baseline justify-between gap-2">
                <p className="font-serif text-4xl leading-none">{position.display}</p>
                <p className="text-xs font-medium text-ink-soft">{plural(position.document_ids.length, 'document')}</p>
              </div>
              <ul className="mt-3 space-y-1.5">
                {position.claim_ids.map((claimId) => {
                  const claim = claims.get(claimId)
                  if (!claim) return null
                  const active = selectedClaimId === claimId
                  return (
                    <li key={claimId}>
                      <button
                        type="button"
                        data-testid="position-source"
                        title="Show the verified evidence"
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
        <p key={i} data-testid="supersession-note" className="mt-3 rounded-md bg-paper p-2.5 text-sm">
          <span className="font-semibold">Possible supersession signal.</span>{' '}
          {displayName(note.evidence.document)} says it replaces or amends an earlier provision:{' '}
          <span className="verified-quote">{note.evidence.quote}</span>{' '}
          <span className="text-xs text-ink-soft">({locationOf(note.evidence)})</span>
        </p>
      ))}
      <p className="mt-3 text-xs font-medium text-red-900">
        Both positions are shown with their sources. No side has been chosen for you.
      </p>
    </div>
  )
}
