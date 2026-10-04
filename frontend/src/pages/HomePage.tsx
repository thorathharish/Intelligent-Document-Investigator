import { BadgeCheck, GitCompare, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateInvestigation, useSeedDemo } from '../api/hooks'
import type { ApiError } from '../api/types'

const CASES = [
  {
    set: 'A' as const,
    testId: 'seed-a',
    action: 'Load contract case',
    title: 'Vendor contract review',
    about: 'A services agreement, its amendment, a scanned invoice and a payment policy. The payment terms do not all agree.',
  },
  {
    set: 'B' as const,
    testId: 'seed-b',
    action: 'Load HR case',
    title: 'HR policy review',
    about: 'An employee handbook, an offer letter and an HR memo. Leave entitlement and remote work are stated differently.',
  },
]

const PROMISES = [
  { Icon: BadgeCheck, text: 'Every quote is checked against the document before you see it.' },
  { Icon: GitCompare, text: 'When documents disagree, both sides are shown. Nothing is picked for you.' },
  { Icon: ShieldAlert, text: 'When the evidence is thin or missing, it says so instead of guessing.' },
]

export function HomePage() {
  const [title, setTitle] = useState('')
  const navigate = useNavigate()
  const create = useCreateInvestigation()
  const seed = useSeedDemo()

  const start = (e: React.FormEvent) => {
    e.preventDefault()
    create.mutate(title, { onSuccess: (investigation) => navigate(`/i/${investigation.id}`) })
  }
  const load = (set: 'A' | 'B') =>
    seed.mutate(set, { onSuccess: (investigation) => navigate(`/i/${investigation.id}`) })

  return (
    <main className="mx-auto max-w-3xl px-6 py-14">
      <p className="text-sm font-semibold text-accent">Document Investigator</p>
      <h1 className="mt-2 font-serif text-4xl leading-tight">
        Answers from your documents, with the proof beside them.
      </h1>
      <ul className="mt-6 space-y-2">
        {PROMISES.map(({ Icon, text }) => (
          <li key={text} className="flex items-start gap-2 text-sm text-ink-soft">
            <Icon size={16} className="mt-0.5 shrink-0 text-ink" aria-hidden />
            {text}
          </li>
        ))}
      </ul>

      <section className="mt-10">
        <h2 className="text-sm font-semibold">Open a demo case</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {CASES.map((item) => (
            <div key={item.set} className="flex flex-col rounded-lg border border-line bg-white p-4">
              <p className="font-serif text-xl">{item.title}</p>
              <p className="mt-1 flex-1 text-sm text-ink-soft">{item.about}</p>
              <button
                type="button"
                data-testid={item.testId}
                disabled={seed.isPending}
                onClick={() => load(item.set)}
                className="mt-4 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-accent disabled:opacity-50"
              >
                {seed.isPending && seed.variables === item.set ? 'Loading…' : item.action}
              </button>
            </div>
          ))}
        </div>
        {seed.isError && (
          <p className="mt-2 text-sm text-red-800">
            The demo case could not be loaded: {(seed.error as unknown as ApiError).message}
          </p>
        )}
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-semibold">Or start with your own documents</h2>
        <form onSubmit={start} className="mt-3 flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Investigation title"
            aria-label="Investigation title"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-lg border border-ink px-4 py-2 text-sm font-medium hover:bg-ink hover:text-white disabled:opacity-50"
          >
            Start investigation
          </button>
        </form>
        {create.isError && (
          <p className="mt-2 text-sm text-red-800">
            The investigation could not be created: {(create.error as unknown as ApiError).message}
          </p>
        )}
      </section>
    </main>
  )
}
