import { GitCompare } from 'lucide-react'
import type { Contradiction } from '../lib/format'

interface Props {
  contradictions: Contradiction[]
  onOpen: (runId: string) => void
}

/** Every conflict found so far in this investigation, at a glance. */
export function ContradictionList({ contradictions, onOpen }: Props) {
  if (contradictions.length === 0) {
    return (
      <p data-testid="no-contradictions" className="rounded-lg border border-line bg-white p-4 text-sm text-ink-soft">
        No conflicting evidence has been found yet. Conflicts appear here when two documents state different
        values for the same fact.
      </p>
    )
  }
  return (
    <ul className="space-y-3">
      {contradictions.map((item) => (
        <li key={item.key} data-testid="contradiction" className="rounded-lg border border-red-200 bg-white p-4">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <GitCompare size={15} className="text-red-800" aria-hidden />
            {item.label}
          </p>
          <table className="mt-2 w-full text-sm">
            <tbody>
              {item.sides.flatMap((side) =>
                side.documents.map((document) => (
                  <tr key={`${side.display}-${document}`} className="border-t border-line">
                    <td className="w-28 py-1.5 pr-3 font-serif text-base">{side.display}</td>
                    <td className="py-1.5 text-ink-soft">{document}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
          <button
            type="button"
            onClick={() => onOpen(item.runId)}
            className="mt-2 text-xs font-medium text-accent hover:underline"
          >
            Open the question that found this: “{item.question}”
          </button>
        </li>
      ))}
    </ul>
  )
}
