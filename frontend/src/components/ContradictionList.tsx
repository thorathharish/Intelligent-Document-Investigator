import { Fragment } from 'react'
import type { Contradiction } from '../lib/format'
import { displayName } from '../lib/format'

interface Props {
  contradictions: Contradiction[]
  onOpen: (runId: string) => void
}

/** Every conflict found so far in this investigation, at a glance. */
export function ContradictionList({ contradictions, onOpen }: Props) {
  if (contradictions.length === 0) {
    return (
      <p data-testid="no-contradictions" className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-ink-soft">
        No conflicting evidence has been found yet. A conflict is listed here when two documents state
        different values for the same fact.
      </p>
    )
  }
  return (
    <ul className="space-y-3">
      {contradictions.map((item) => (
        <li key={item.key} data-testid="contradiction" className="rounded-lg border border-red-200 bg-white p-4">
          <p className="font-serif text-xl text-red-900">{item.label.trim() || 'Conflicting values'}</p>
          <div className="mt-2 flex flex-wrap items-stretch gap-2">
            {item.sides.map((side, i) => (
              <Fragment key={side.display}>
                {i > 0 && (
                  <div className="flex items-center font-serif text-2xl font-semibold text-red-700" aria-label="conflicts with">
                    ≠
                  </div>
                )}
                <div className="min-w-[180px] flex-1 rounded-md border border-line bg-paper px-3 py-2">
                  <p className="font-serif text-2xl leading-tight">{side.display}</p>
                  <ul className="mt-1 text-sm text-ink-soft">
                    {side.documents.map((document) => (
                      <li key={document}>{displayName(document)}</li>
                    ))}
                  </ul>
                </div>
              </Fragment>
            ))}
          </div>
          <button
            type="button"
            onClick={() => onOpen(item.runId)}
            className="mt-3 text-xs font-medium text-accent hover:underline"
          >
            Found by the question “{item.question}”. Open it with its evidence
          </button>
        </li>
      ))}
    </ul>
  )
}
