import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateInvestigation, useSeedDemo } from '../api/hooks'
import type { ApiError } from '../api/types'

export function HomePage() {
  const [title, setTitle] = useState('')
  const navigate = useNavigate()
  const create = useCreateInvestigation()
  const seed = useSeedDemo()

  const load = (set: 'A' | 'B') =>
    seed.mutate(set, { onSuccess: (investigation) => navigate(`/i/${investigation.id}`) })

  const start = (e: React.FormEvent) => {
    e.preventDefault()
    create.mutate(title, { onSuccess: (investigation) => navigate(`/i/${investigation.id}`) })
  }

  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">Document Investigator</h1>
      <p className="mt-2 text-sm text-slate-600">
        Ask questions across your documents. Every answer is checked against the source text.
      </p>
      <form onSubmit={start} className="mt-6 flex gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Investigation title"
          className="flex-1 rounded border border-slate-300 bg-white px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Start investigation
        </button>
      </form>
      {create.isError && (
        <p className="mt-2 text-sm text-red-700">{(create.error as unknown as ApiError).message}</p>
      )}

      <div className="mt-8 border-t border-slate-200 pt-4">
        <p className="text-sm text-slate-600">Or open a demo case with documents already loaded:</p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            data-testid="seed-a"
            disabled={seed.isPending}
            onClick={() => load('A')}
            className="rounded border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50"
          >
            Load contract case (Set A)
          </button>
          <button
            type="button"
            data-testid="seed-b"
            disabled={seed.isPending}
            onClick={() => load('B')}
            className="rounded border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50"
          >
            Load HR case (Set B)
          </button>
        </div>
        {seed.isError && (
          <p className="mt-2 text-sm text-red-700">{(seed.error as unknown as ApiError).message}</p>
        )}
      </div>
    </main>
  )
}
