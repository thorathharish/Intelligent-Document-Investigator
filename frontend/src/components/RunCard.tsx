import { TriangleAlert } from 'lucide-react'
import type { RunResult } from '../api/types'
import { timeOf } from '../lib/format'
import { ContradictionMap } from './ContradictionMap'
import { STATES, StateBadge } from './StateBadge'
import { WhyThisAnswer } from './WhyThisAnswer'

interface Props {
  run: RunResult
  selected: boolean
  selectedClaimId: string | null
  onSelect: () => void
  onSelectClaim: (claimId: string) => void
}

const NO_ANSWER = "I couldn't find verified evidence sufficient to answer this question."
const EVIDENCE_ONLY = 'Evidence is available, but automatic analysis was unavailable. The closest passages are shown as evidence.'

export function RunCard({ run, selected, selectedClaimId, onSelect, onSelectClaim }: Props) {
  // earlier questions stay in the list as one-line history rows
  if (!selected) {
    return (
      <button
        type="button"
        data-testid="run-card"
        data-collapsed="true"
        onClick={onSelect}
        className="flex w-full items-center gap-3 rounded-lg border border-line bg-white px-4 py-2.5 text-left hover:border-accent"
      >
        <span className="min-w-0 flex-1 truncate text-sm" data-testid="run-question">
          {run.question}
        </span>
        <span className="shrink-0 text-xs text-ink-soft">{timeOf(run.created_at)}</span>
        <StateBadge state={run.state} compact />
      </button>
    )
  }

  const claimById = new Map(run.claims.map((c) => [c.id, c]))
  const conflicts = run.aspects.filter((a) => a.status === 'conflict')

  return (
    <article data-testid="run-card" className="rounded-lg border border-slate-300 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="min-w-0 flex-1 text-base font-semibold" data-testid="run-question">
          {run.question}
        </h3>
        <StateBadge state={run.state} />
      </div>
      <p className="mt-1 text-xs text-ink-soft">
        {STATES[run.state].meaning}
        {run.cached && <span data-testid="cached"> Answered earlier; shown from this investigation's history.</span>}
      </p>

      {run.degraded && (
        <p data-testid="degraded" className="mt-4 flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden />
          {EVIDENCE_ONLY}
        </p>
      )}

      {run.state === 'INSUFFICIENT' && (
        <p data-testid="no-answer" className="mt-4 rounded-md bg-slate-100 p-3 font-serif text-lg text-slate-800">
          {NO_ANSWER}
        </p>
      )}

      {conflicts.map((aspect) => (
        <ContradictionMap
          key={aspect.id}
          aspect={aspect}
          claims={claimById}
          selectedClaimId={selectedClaimId}
          onSelectClaim={onSelectClaim}
        />
      ))}

      {run.answer.length > 0 && (
        <div className="mt-4 space-y-2 font-serif text-lg leading-relaxed" data-testid="answer">
          {run.answer.map((sentence, i) => (
            <p key={i}>
              {sentence.text}{' '}
              {sentence.claim_ids.map((claimId) => (
                <button
                  key={claimId}
                  type="button"
                  data-testid="citation"
                  title="Show the verified evidence"
                  onClick={() => onSelectClaim(claimId)}
                  className={`mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded px-1 align-middle font-sans text-xs font-semibold transition-colors ${
                    selectedClaimId === claimId ? 'bg-ink text-white' : 'bg-blue-100 text-accent hover:bg-blue-200'
                  }`}
                >
                  {claimById.get(claimId)?.citation}
                </button>
              ))}
            </p>
          ))}
        </div>
      )}

      {run.warnings.length > 0 && (
        <ul data-testid="warnings" className="mt-3 space-y-1">
          {run.warnings.map((warning, i) => (
            <li key={i} className="flex items-center gap-1.5 text-xs text-amber-800">
              <TriangleAlert size={12} aria-hidden /> {warning}
            </li>
          ))}
        </ul>
      )}

      <WhyThisAnswer run={run} />
    </article>
  )
}
