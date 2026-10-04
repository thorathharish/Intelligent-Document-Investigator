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
  const hasAnswer = run.answer.length > 0

  return (
    <article
      onClick={onSelect}
      data-testid="run-card"
      className={`cursor-pointer rounded border bg-white p-4 ${selected ? 'border-slate-900' : 'border-slate-200'}`}
    >
      <p className="text-xs uppercase tracking-wide text-slate-500">Question</p>
      <h3 className="font-medium">{run.question}</h3>

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
