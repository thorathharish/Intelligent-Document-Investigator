import type { RunResult } from '../api/types'

interface Props {
  run: RunResult
  selected: boolean
  selectedClaimId: string | null
  onSelect: () => void
  onSelectClaim: (claimId: string) => void
}

export function RunCard({ run, selected, selectedClaimId, onSelect, onSelectClaim }: Props) {
  const citation = new Map(run.claims.map((c) => [c.id, c.citation]))
  const claimById = new Map(run.claims.map((c) => [c.id, c]))
  const conflicts = run.aspects.filter((a) => a.status === 'conflict')
  const hasAnswer = run.answer.length > 0

  return (
    <article
      onClick={onSelect}
      data-testid="run-card"
      className={`cursor-pointer rounded border bg-white p-4 ${selected ? 'border-slate-900' : 'border-slate-200'}`}
    >
      <p className="text-xs uppercase tracking-wide text-slate-500">Question</p>
      <h3 className="font-medium">{run.question}</h3>

      {run.state === 'CONFLICT' && (
        <div data-testid="conflict" className="mt-3 rounded border border-red-300 bg-red-50 p-3 text-sm">
          <p className="font-semibold text-red-800">Conflict detected</p>
          <p className="text-red-900">{run.headline}</p>
          {conflicts.map((aspect) => (
            <div key={aspect.id} className="mt-2">
              <p className="text-xs uppercase tracking-wide text-red-800">{aspect.label}</p>
              <ul className="mt-1 space-y-1">
                {aspect.positions.map((position) => (
                  <li key={position.key} data-testid="position" className="rounded bg-white p-2">
                    <span className="font-semibold">{position.display}</span>
                    <span className="text-xs text-slate-500">
                      {' '}
                      · {position.document_ids.length} document{position.document_ids.length === 1 ? '' : 's'}
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {position.claim_ids.map((claimId) => {
                        const claim = claimById.get(claimId)
                        if (!claim) return null
                        return (
                          <button
                            key={claimId}
                            type="button"
                            data-testid="position-source"
                            onClick={(e) => {
                              e.stopPropagation()
                              onSelect()
                              onSelectClaim(claimId)
                            }}
                            className={`rounded border px-1.5 py-0.5 text-xs ${
                              selected && selectedClaimId === claimId
                                ? 'border-slate-900 bg-slate-900 text-white'
                                : 'border-slate-300 bg-slate-50'
                            }`}
                          >
                            {claim.evidence.document}
                            {claim.evidence.page != null && ` · p.${claim.evidence.page}`}
                          </button>
                        )
                      })}
                    </div>
                  </li>
                ))}
              </ul>
              {aspect.notes.map((note, i) => (
                <p key={i} data-testid="supersession-note" className="mt-2 text-xs text-slate-700">
                  Note: {note.text} “{note.evidence.quote}”
                  {note.evidence.page != null && ` (page ${note.evidence.page})`}. Both positions are still shown
                  so you can decide.
                </p>
              ))}
            </div>
          ))}
        </div>
      )}

      {!hasAnswer && (
        <p data-testid="no-answer" className="mt-3 rounded bg-slate-100 p-2 text-sm text-slate-700">
          {run.headline}
        </p>
      )}

      {hasAnswer && (
        <div className="mt-3 space-y-1 text-sm" data-testid="answer">
          {run.answer.map((sentence, i) => (
            <p key={i}>
              {sentence.text}{' '}
              {sentence.claim_ids.map((claimId) => (
                <button
                  key={claimId}
                  type="button"
                  data-testid="citation"
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelect()
                    onSelectClaim(claimId)
                  }}
                  className={`mx-0.5 rounded px-1.5 text-xs font-semibold ${
                    selected && selectedClaimId === claimId ? 'bg-slate-900 text-white' : 'bg-blue-100 text-blue-900'
                  }`}
                >
                  {citation.get(claimId)}
                </button>
              ))}
            </p>
          ))}
        </div>
      )}

      {run.warnings.map((warning, i) => (
        <p key={i} className="mt-2 text-xs text-amber-800">
          {warning}
        </p>
      ))}
    </article>
  )
}
