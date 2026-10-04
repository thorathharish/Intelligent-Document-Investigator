import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import type { RunResult } from '../api/types'
import { plural } from '../lib/format'
import { InfoTip } from './InfoTip'
import { STATES } from './StateBadge'

/** Explains the evidence state from the backend's rule-based reasons and counts. No model reasoning is shown. */
export function WhyThisAnswer({ run }: { run: RunResult }) {
  const [open, setOpen] = useState(false)
  const num = (key: string) => Number(run.signals[key] ?? 0)
  const facts = [
    plural(num('claims_verified'), 'verified passage'),
    plural(num('documents_cited'), 'supporting document'),
    num('explicit_claims') > 0 ? `${num('explicit_claims')} stated directly` : null,
    num('inferred_claims') > 0 ? `${num('inferred_claims')} inferred` : null,
    num('ocr_claims') > 0 ? `${num('ocr_claims')} from scans` : null,
    num('conflicting_aspects') > 0 ? plural(num('conflicting_aspects'), 'conflict') : null,
    num('aspects_uncovered') > 0 ? `${num('aspects_uncovered')} part${num('aspects_uncovered') === 1 ? '' : 's'} unanswered` : null,
    num('claims_dropped') > 0 ? `${num('claims_dropped')} discarded as unverifiable` : null,
  ].filter(Boolean)

  return (
    <div className="mt-4 border-t border-line pt-3">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          data-testid="why-toggle"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="shrink-0 text-left text-sm font-semibold"
        >
          Why this answer?
        </button>
        <InfoTip
          label="Why this answer"
          text="Shows the evidence-based signals used to describe how well the available sources support this answer."
        />
        {/* the counts and chevron toggle too; the labelled button above is the one keyboard users reach */}
        <button
          type="button"
          tabIndex={-1}
          aria-hidden="true"
          onClick={() => setOpen(!open)}
          className="ml-1.5 flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <span data-testid="signals" className="flex min-w-0 flex-1 flex-wrap gap-1.5">
            {facts.map((fact) => (
              <span key={fact} className="rounded bg-paper px-2 py-0.5 text-xs text-ink-soft">
                {fact}
              </span>
            ))}
          </span>
          <ChevronDown size={16} className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>
      {open && (
        <div data-testid="why" className="mt-3 text-sm">
          <p>
            <span className="font-semibold">{run.state}</span>
            <span className="text-ink-soft"> — {STATES[run.state].meaning}</span>
          </p>
          <ul data-testid="reasons" className="mt-2 list-disc space-y-1 pl-5">
            {run.reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-ink-soft">
            This rating is calculated by fixed rules over the checked evidence, not by the language model.
          </p>
        </div>
      )}
    </div>
  )
}
