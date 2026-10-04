import { LoaderCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAskQuestion, useDocuments, useInvestigation, useRuns } from '../api/hooks'
import type { ApiError } from '../api/types'
import { ContradictionList } from '../components/ContradictionList'
import { DocumentsPane } from '../components/DocumentsPane'
import { EvidencePane } from '../components/EvidencePane'
import { QuestionBar } from '../components/QuestionBar'
import { RunCard } from '../components/RunCard'
import { contradictionsOf, plural } from '../lib/format'

type Tab = 'questions' | 'contradictions'

export function WorkspacePage() {
  const { investigationId = '' } = useParams()
  const investigation = useInvestigation(investigationId)
  const documents = useDocuments(investigationId)
  const runs = useRuns(investigationId)
  const ask = useAskQuestion(investigationId)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('questions')
  const bottom = useRef<HTMLDivElement>(null)

  const allRuns = useMemo(() => runs.data ?? [], [runs.data])
  const contradictions = useMemo(() => contradictionsOf(allRuns), [allRuns])
  const selectedRun = allRuns.find((r) => r.run_id === selectedRunId) ?? allRuns[allRuns.length - 1] ?? null
  const hasReadyDocument = documents.data?.some((d) => d.status === 'ready') ?? false

  useEffect(() => {
    if (ask.isPending) bottom.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [ask.isPending])

  if (investigation.isError) {
    return (
      <main className="mx-auto max-w-xl px-6 py-14">
        <h1 className="font-serif text-2xl">This investigation could not be found.</h1>
        <p className="mt-2 text-sm text-ink-soft">It may have been removed, or the link is incomplete.</p>
        <Link to="/" className="mt-4 inline-block text-sm font-medium text-accent hover:underline">
          Back to the start page
        </Link>
      </main>
    )
  }

  const selectRun = (runId: string) => {
    if (runId !== selectedRun?.run_id) setSelectedClaimId(null)
    setSelectedRunId(runId)
    setTab('questions')
  }

  const onAsk = (question: string) => {
    setTab('questions')
    ask.mutate(question, {
      onSuccess: (run) => {
        setSelectedRunId(run.run_id)
        setSelectedClaimId(null)
      },
    })
  }

  const tabClass = (name: Tab) =>
    `border-b-2 px-1 pb-2 text-sm font-semibold ${
      tab === name ? 'border-ink text-ink' : 'border-transparent text-ink-soft hover:text-ink'
    }`

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between gap-4 border-b border-line bg-white px-5 py-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-accent">Document Investigator</p>
          <h1 className="truncate font-serif text-2xl leading-tight" data-testid="investigation-title">
            {investigation.data?.title ?? 'Loading…'}
          </h1>
        </div>
        <div className="flex shrink-0 items-center gap-4 text-xs text-ink-soft">
          <span>{plural(documents.data?.length ?? 0, 'document')}</span>
          <span>{plural(allRuns.length, 'question')}</span>
          <span className={contradictions.length > 0 ? 'font-semibold text-red-800' : ''}>
            {plural(contradictions.length, 'conflict')} found
          </span>
          <Link to="/" className="rounded-lg border border-line px-3 py-1.5 font-medium text-ink hover:border-accent">
            Switch case
          </Link>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)_400px] max-[1100px]:grid-cols-[240px_minmax(0,1fr)] max-[1100px]:grid-rows-[minmax(0,1fr)_minmax(0,40%)]">
        <aside className="min-h-0 border-r border-line bg-white p-4 max-[1100px]:row-span-2">
          <DocumentsPane investigationId={investigationId} />
        </aside>

        <section className="flex min-h-0 flex-col">
          <div className="flex gap-5 border-b border-line bg-white px-5 pt-3" role="tablist">
            <button type="button" role="tab" aria-selected={tab === 'questions'} className={tabClass('questions')} onClick={() => setTab('questions')}>
              Investigation
            </button>
            <button
              type="button"
              role="tab"
              data-testid="tab-contradictions"
              aria-selected={tab === 'contradictions'}
              className={tabClass('contradictions')}
              onClick={() => setTab('contradictions')}
            >
              Contradictions{contradictions.length > 0 && ` (${contradictions.length})`}
            </button>
          </div>

          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-5 py-4">
            {tab === 'contradictions' && <ContradictionList contradictions={contradictions} onOpen={selectRun} />}

            {tab === 'questions' && (
              <>
                {runs.isLoading && <p className="text-sm text-ink-soft">Loading earlier questions…</p>}
                {runs.isError && <p className="text-sm text-red-800">Earlier questions could not be loaded.</p>}
                {runs.isSuccess && allRuns.length === 0 && !ask.isPending && (
                  <div data-testid="empty-investigation" className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-ink-soft">
                    {hasReadyDocument
                      ? 'Ask a question below. The answer appears here with its evidence state, and the passages behind it appear on the right.'
                      : 'Add documents on the left. Questions can be asked as soon as one is ready.'}
                  </div>
                )}
                {allRuns.map((run) => (
                  <RunCard
                    key={run.run_id}
                    run={run}
                    selected={run.run_id === selectedRun?.run_id && !ask.isPending}
                    selectedClaimId={selectedClaimId}
                    onSelect={() => selectRun(run.run_id)}
                    onSelectClaim={setSelectedClaimId}
                  />
                ))}
                {ask.isPending && (
                  <div data-testid="pending" className="rounded-lg border border-slate-300 bg-white p-5">
                    <p className="text-base font-semibold">{ask.variables}</p>
                    <p className="mt-2 flex items-center gap-2 text-sm text-ink-soft">
                      <LoaderCircle size={16} className="animate-spin" aria-hidden />
                      Retrieving evidence, checking quotes and comparing documents…
                    </p>
                  </div>
                )}
                {ask.isError && (
                  <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">
                    The question could not be investigated: {(ask.error as unknown as ApiError).message}
                  </p>
                )}
                <div ref={bottom} />
              </>
            )}
          </div>

          <QuestionBar disabled={!hasReadyDocument} pending={ask.isPending} onAsk={onAsk} />
        </section>

        <aside className="min-h-0 border-l border-line p-4 max-[1100px]:border-l-0 max-[1100px]:border-t">
          <EvidencePane
            run={ask.isPending ? null : selectedRun}
            selectedClaimId={selectedClaimId}
            onSelectClaim={setSelectedClaimId}
          />
        </aside>
      </div>
    </div>
  )
}
