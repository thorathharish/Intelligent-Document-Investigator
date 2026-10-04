import { useEffect, useRef } from 'react'
import type { RunResult } from '../api/types'
import { plural } from '../lib/format'
import { InfoTip } from './InfoTip'
import { StateTag } from './StateBadge'

interface Props {
  runs: RunResult[]
  selectedRunId: string | null
  onSelect: (runId: string) => void
}

/** Earlier questions as compact rows; the selected one is shown in full below the list. */
export function HistoryList({ runs, selectedRunId, onSelect }: Props) {
  const selected = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    selected.current?.scrollIntoView({ block: 'nearest' })
  }, [selectedRunId, runs.length])

  return (
    <section aria-label="Questions asked" className="rounded-lg border border-line bg-white">
      <p className="flex items-center gap-1 border-b border-line px-3 py-1.5 text-xs font-semibold text-ink-soft">
        {plural(runs.length, 'question')} asked
        <InfoTip
          label="History"
          text="Questions asked in this investigation. Select one to review its answer and supporting evidence."
        />
      </p>
      <ul className="max-h-[7.75rem] overflow-y-auto">
        {runs.map((run) => {
          const active = run.run_id === selectedRunId
          return (
            <li key={run.run_id}>
              <button
                type="button"
                ref={active ? selected : undefined}
                data-testid="history-row"
                aria-current={active ? 'true' : undefined}
                onClick={() => onSelect(run.run_id)}
                className={`flex w-full items-center gap-3 border-l-[3px] px-3 py-1.5 text-left text-sm ${
                  active ? 'border-ink bg-paper font-medium' : 'border-transparent hover:bg-paper'
                }`}
              >
                <StateTag state={run.state} />
                <span className="min-w-0 flex-1 truncate">{run.question}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
