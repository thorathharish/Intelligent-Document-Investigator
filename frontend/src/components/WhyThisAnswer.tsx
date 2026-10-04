import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import type { RunResult } from '../api/types'
import { plural } from '../lib/format'
import { STATES } from './StateBadge'

/** Explains the evidence state from the backend's rule-based reasons and counts. No model reasoning is shown. */
export function WhyThisAnswer({ run }: { run: RunResult }) {
  const [open, setOpen] = useState(run.state !== 'HIGH')
  const s = run.signals
  const num = (key: string) => Number(s[key] ?? 0)
  const facts = [
    plural(num('claims_verified'), 'verified passage'),
    plural(num('documents_cited'), 'document'),
    num('explicit_claims') > 0 ? `${num('explicit_claims')} stated directly` : null,
    num('inferred_claims') > 0 ? `${num('inferred_claims')} inferred` : null,
    num('ocr_claims') > 0 ? `${num('ocr_claims')} from scans` : null,
    num('conflicting_aspects') > 0 ? plural(num('conflicting_aspects'), 'conflict') : null,
    num('aspects_uncovered') > 0 ? `${num('aspects_uncovered')} part${num('aspects_uncovered') === 1 ? '' : 's'} unanswered` : null,
    num('claims_dropped') > 0 ? `${num('claims_dropped')} discarded as unverifiable` : null,
  ].filter(Boolean)

  return (
    <div className="mt-4 border-t border-line pt-3">
      <button
        type="button"
        data-testid="why-toggle"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation()
          setOpen(!open)
        }}
        className="flex w-full items-center justify-between text-left text-sm font-semibold"
      >
        Why this answer?
        <ChevronDown size={16} className={`transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      {open && (
        <div data-testid="why" className="mt-2 text-sm">
          <p className="text-ink-soft">
            {STATES[run.state].label}: {STATES[run.state].meaning.charAt(0).toLowerCase() + STATES[run.state].meaning.slice(1)}
          </p>
          <ul data-testid="reasons" className="mt-2 list-disc space-y-1 pl-5">
            {run.reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
          <p data-testid="signals" className="mt-3 flex flex-wrap gap-1.5">
            {facts.map((fact) => (
              <span key={fact} className="rounded bg-paper px-2 py-0.5 text-xs text-ink-soft">
                {fact}
              </span>
            ))}
          </p>
          <p className="mt-2 text-xs text-ink-soft">
            This rating is computed by fixed rules from the checked evidence, not by the language model.
          </p>
        </div>
      )}
    </div>
  )
}
