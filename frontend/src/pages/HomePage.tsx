import { BadgeCheck, CircleHelp, FileCheck, GitCompare } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useCreateInvestigation, useSeedDemo } from '../api/hooks'
import type { ApiError } from '../api/types'
import { StateBadge } from '../components/StateBadge'

const DIFFERENTIATORS = [
  {
    Icon: BadgeCheck,
    title: 'Evidence-first answers',
    text: 'Every answer is tied to verified source passages from the documents.',
  },
  {
    Icon: GitCompare,
    title: 'Detects contradictions',
    text: 'When documents disagree, the system shows both positions instead of silently choosing one.',
  },
  {
    Icon: CircleHelp,
    title: 'Knows when evidence is insufficient',
    text: 'The system can say when the available documents do not support a reliable answer.',
  },
]

const STEPS = [
  { title: 'Upload documents', text: 'PDF, Word, text, and scanned images.' },
  { title: 'Ask a question', text: 'Use natural language to investigate the documents.' },
  { title: 'Verify the evidence', text: 'Relevant source passages are checked before they support the answer.' },
  {
    title: 'See conflicts and uncertainty',
    text: 'Compare conflicting evidence and understand when the answer is limited.',
  },
]

// The contract demo case, as the workspace shows it. Used only to illustrate the product.
const PREVIEW_EVIDENCE = [
  {
    document: 'Master Services Agreement',
    location: 'Page 2 · 4.2 Payment Terms',
    quote: 'within thirty (30) days of the invoice date',
  },
  { document: 'Amendment 1', location: 'Page 1 · 1. Payment Terms', quote: 'within 30 days of the invoice date' },
  { document: 'Invoice INV-2041', location: 'Page 1 · scanned', quote: 'Payment due within 45 days of the invoice date' },
]

function PositionBox({ value, sources }: { value: string; sources: string[] }) {
  return (
    <div className="min-w-0 flex-1 rounded-lg border-2 border-red-200 bg-white p-2.5 sm:p-3">
      <p className="font-serif text-2xl leading-none sm:text-3xl">{value}</p>
      <ul className="mt-2 space-y-0.5 text-sm text-ink-soft">
        {sources.map((source) => (
          <li key={source}>{source}</li>
        ))}
      </ul>
    </div>
  )
}

function Conflict() {
  return (
    <div className="flex items-stretch gap-2">
      <PositionBox value="30 days" sources={['Master Services Agreement', 'Amendment 1']} />
      <div className="flex shrink-0 items-center font-serif text-2xl font-semibold text-red-700 sm:text-3xl" aria-label="conflicts with">
        ≠
      </div>
      <PositionBox value="45 days" sources={['Invoice INV-2041']} />
    </div>
  )
}

export function HomePage() {
  const navigate = useNavigate()
  const create = useCreateInvestigation()
  const seed = useSeedDemo()
  const busy = create.isPending || seed.isPending

  const start = () =>
    create.mutate('New investigation', { onSuccess: (investigation) => navigate(`/i/${investigation.id}`) })
  const load = (set: 'A' | 'B') =>
    seed.mutate(set, { onSuccess: (investigation) => navigate(`/i/${investigation.id}`) })
  const failure = (create.error ?? seed.error) as unknown as ApiError | null

  const primary =
    'rounded-lg bg-ink px-5 py-3 text-sm font-semibold text-white hover:bg-accent disabled:opacity-50 transition-colors'
  // every section shares this container, so their left and right edges line up at any width
  const container = 'mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8'
  const secondary =
    'rounded-lg border border-slate-400 bg-white px-5 py-3 text-sm font-semibold hover:border-accent disabled:opacity-50 transition-colors'

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-line bg-white">
        <nav className={`${container} flex items-center justify-between gap-3 py-3`} aria-label="Main">
          <p className="flex items-center gap-2 whitespace-nowrap text-lg font-bold leading-none tracking-tight sm:text-xl">
            <FileCheck size={22} className="shrink-0 text-accent" aria-hidden />
            Document Investigator
          </p>
          <button type="button" onClick={start} disabled={busy} className="shrink-0 text-sm font-semibold text-accent hover:underline">
            Start investigating
          </button>
        </nav>
      </header>

      <main>
        {/* hero */}
        <section className={`${container} grid items-center gap-8 py-10 sm:py-14 lg:grid-cols-[1.05fr_1fr] lg:gap-10`}>
          <div className="min-w-0">
            <h1 className="font-serif text-4xl leading-[1.08] sm:text-5xl xl:text-6xl">Answers you can verify.</h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-ink-soft sm:mt-5 sm:text-lg">
              Investigate scattered documents with evidence-backed answers, conflict detection, and clear
              uncertainty.
            </p>
            <div className="mt-6 flex flex-wrap gap-3 sm:mt-8">
              <button type="button" data-testid="start" onClick={start} disabled={busy} className={primary}>
                {create.isPending ? 'Opening…' : 'Start investigating'}
              </button>
              <button type="button" data-testid="seed-a" onClick={() => load('A')} disabled={busy} className={secondary}>
                {seed.isPending && seed.variables === 'A' ? 'Loading the case…' : 'Try demo case'}
              </button>
            </div>
            <p className="mt-4 flex items-center gap-1.5 text-sm text-ink-soft">
              <BadgeCheck size={15} className="text-emerald-700" aria-hidden />
              Answers are checked against the source documents.
            </p>
            {failure && (
              <p role="alert" className="mt-3 text-sm text-red-800">
                That could not be opened: {failure.message}
              </p>
            )}
          </div>

          <figure className="min-w-0 rounded-xl border border-t-4 border-slate-300 border-t-red-600 bg-white p-4 shadow-sm sm:p-6">
            <p className="text-xs font-semibold text-ink-soft">Question</p>
            <p className="mt-0.5 text-lg font-semibold">What payment terms apply?</p>
            <div className="mt-3">
              <StateBadge state="CONFLICT" />
            </div>
            <p className="mt-4 font-serif text-lg text-red-900 sm:text-xl">Evidence disagrees on the payment period</p>
            <div className="mt-3">
              <Conflict />
            </div>
            <p className="mt-4 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 border-t border-line pt-3 text-sm">
              <BadgeCheck size={15} className="text-emerald-700" aria-hidden />
              <span className="font-semibold">Verified evidence</span>
              <span className="text-ink-soft">3 source passages verified. No side chosen.</span>
            </p>
            <figcaption className="mt-3 text-xs text-ink-soft">
              Preview of a result from the contract demo case.
            </figcaption>
          </figure>
        </section>

        {/* differentiators */}
        <section className="border-y border-line bg-white" aria-labelledby="different">
          <div className={`${container} py-10 sm:py-12`}>
            <h2 id="different" className="font-serif text-2xl sm:text-3xl">
              It investigates. It does not just answer.
            </h2>
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {DIFFERENTIATORS.map(({ Icon, title, text }) => (
                <div key={title} className="rounded-lg border border-line bg-paper p-5">
                  <Icon size={22} className="text-accent" aria-hidden />
                  <h3 className="mt-3 font-semibold">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* how it works */}
        <section className={`${container} py-10 sm:py-12`} aria-labelledby="how">
          <h2 id="how" className="font-serif text-2xl sm:text-3xl">
            How it works
          </h2>
          <ol className="mt-6 grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="border-t-2 border-ink pt-3">
                <p className="font-serif text-2xl text-ink-soft">{String(i + 1).padStart(2, '0')}</p>
                <h3 className="mt-1 font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-soft">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* product preview */}
        <section className="border-y border-line bg-white" aria-labelledby="preview">
          <div className={`${container} py-10 sm:py-12`}>
            <h2 id="preview" className="font-serif text-2xl sm:text-3xl">
              From question to evidence
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-ink-soft">
              One question in the contract demo case. The answer, the conflict and the passages behind it stay
              side by side, so you can check every step.
            </p>
            <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_1fr]">
              <div className="min-w-0 rounded-lg border border-line bg-paper p-4 sm:p-5">
                <p className="text-xs font-semibold text-ink-soft">Question</p>
                <p className="mt-0.5 font-semibold">What payment terms apply?</p>
                <p className="mt-4 text-xs font-semibold text-ink-soft">Answer</p>
                <div className="mt-1">
                  <StateBadge state="CONFLICT" />
                </div>
                <p className="mt-3 font-serif text-lg leading-relaxed">
                  Master Services Agreement and Amendment 1 state 30 days. Invoice INV-2041 states 45 days.
                </p>
                <div className="mt-4">
                  <Conflict />
                </div>
              </div>
              <div className="min-w-0 rounded-lg border border-line bg-paper p-4 sm:p-5">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <BadgeCheck size={16} className="text-emerald-700" aria-hidden />
                  Verified evidence
                </p>
                <ul className="mt-3 space-y-3">
                  {PREVIEW_EVIDENCE.map((item, i) => (
                    <li key={item.document} className="rounded-lg border border-line bg-white p-3">
                      <p className="text-sm font-semibold">
                        <span className="mr-2 inline-flex h-5 min-w-5 items-center justify-center rounded bg-blue-50 px-1 text-xs text-accent">
                          {i + 1}
                        </span>
                        {item.document}
                      </p>
                      <p className="text-xs text-ink-soft">{item.location}</p>
                      <p className="mt-2 text-sm">
                        <span className="verified-quote">{item.quote}</span>
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* demo call to action */}
        <section className={`${container} py-12 text-center sm:py-14`} aria-labelledby="try">
          <h2 id="try" className="font-serif text-3xl sm:text-4xl">
            See the investigation for yourself.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-ink-soft">
            Start with a vendor contract case containing agreements, amendments, a policy, and a scanned invoice.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button type="button" data-testid="seed-a-bottom" onClick={() => load('A')} disabled={busy} className={primary}>
              Try the contract case
            </button>
            <button type="button" data-testid="seed-b" onClick={() => load('B')} disabled={busy} className={secondary}>
              {seed.isPending && seed.variables === 'B' ? 'Loading the case…' : 'Try the HR case'}
            </button>
          </div>
          <p className="mt-3 text-xs text-ink-soft">
            The HR case is an unrelated set of documents handled by the same system.
          </p>
        </section>
      </main>

      <footer className="border-t border-line bg-white">
        <div className={`${container} flex flex-wrap items-center justify-between gap-2 py-5 text-sm`}>
          <p className="font-semibold">Document Investigator</p>
          <p className="text-ink-soft">Evidence-backed document investigation.</p>
        </div>
      </footer>
    </div>
  )
}
