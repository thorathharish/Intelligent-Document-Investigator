import { FileCheck, TriangleAlert } from 'lucide-react'
import type { RunResult } from '../api/types'
import { displayName, locationOf, withDisplayNames } from '../lib/format'
import { ContradictionMap } from './ContradictionMap'
import { STATES, StateBadge } from './StateBadge'
import { WhyThisAnswer } from './WhyThisAnswer'

interface Props {
  run: RunResult
  selectedClaimId: string | null
  onSelectClaim: (claimId: string) => void
}

const NO_ANSWER = "I couldn't find verified evidence sufficient to answer this question."
const EVIDENCE_ONLY =
  'Evidence is available, but automatic analysis was unavailable. The closest passages are shown as evidence, not as an answer.'

const EDGE: Record<RunResult['state'], string> = {
  HIGH: 'border-t-emerald-600',
  MEDIUM: 'border-t-sky-600',
  LOW: 'border-t-amber-500',
  CONFLICT: 'border-t-red-600',
  INSUFFICIENT: 'border-t-slate-400',
}

/** The selected investigation: question, evidence state, answer, citations and the reasons behind the state. */
export function RunCard({ run, selectedClaimId, onSelectClaim }: Props) {
  const claimById = new Map(run.claims.map((c) => [c.id, c]))
  const conflicts = run.aspects.filter((a) => a.status === 'conflict')
  const filenames = [...new Set(run.claims.map((c) => c.evidence.document))]

  return (
    <article
      data-testid="run-card"
      className={`rounded-lg border border-t-4 border-slate-300 bg-white p-6 shadow-sm ${EDGE[run.state]}`}
    >
      <h3 className="text-lg font-semibold leading-snug" data-testid="run-question">
        {run.question}
      </h3>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <StateBadge state={run.state} />
        <p className="text-sm text-ink-soft">{STATES[run.state].meaning}</p>
      </div>
      {run.cached && (
        <p data-testid="cached" className="mt-1.5 text-xs text-ink-soft">
          Answered earlier in this investigation; shown from its history.
        </p>
      )}

      {run.degraded && (
        <p data-testid="degraded" className="mt-4 flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden />
          {EVIDENCE_ONLY}
        </p>
      )}

      {run.state === 'INSUFFICIENT' && (
        <div data-testid="no-answer" className="mt-4 rounded-md bg-slate-100 p-4">
          <p className="font-serif text-xl text-slate-800">{NO_ANSWER}</p>
          <p className="mt-1 text-sm text-ink-soft">
            {run.related.length > 0
              ? 'The closest passages are listed under Verified evidence so you can check for yourself.'
              : 'Nothing in the documents is close to this question.'}
          </p>
        </div>
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
        <div
          className={`mt-4 space-y-2 font-serif leading-relaxed ${conflicts.length > 0 ? 'text-base text-ink-soft' : 'text-xl'}`}
          data-testid="answer"
        >
          {run.answer.map((sentence, i) => (
            <p key={i}>
              {withDisplayNames(sentence.text, filenames)}{' '}
              {sentence.claim_ids.map((claimId) => {
                const claim = claimById.get(claimId)
                if (!claim) return null
                const active = selectedClaimId === claimId
                return (
                  <button
                    key={claimId}
                    type="button"
                    data-testid="citation"
                    title={`Verified evidence ${claim.citation}: ${displayName(claim.evidence.document)}, ${locationOf(claim.evidence)}`}
                    onClick={() => onSelectClaim(claimId)}
                    className={`mx-0.5 inline-flex h-6 items-center gap-1 rounded-md border px-1.5 align-middle font-sans text-xs font-semibold transition-colors ${
                      active
                        ? 'border-ink bg-ink text-white'
                        : 'border-blue-200 bg-blue-50 text-accent hover:border-accent'
                    }`}
                  >
                    <FileCheck size={12} aria-hidden />
                    {claim.citation}
                  </button>
                )
              })}
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

      <WhyThisAnswer key={run.run_id} run={run} />
    </article>
  )
}
