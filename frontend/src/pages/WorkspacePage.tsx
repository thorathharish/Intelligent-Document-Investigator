import { BadgeCheck, FileText, GitCompare, LoaderCircle, MessageSquareText, ShieldAlert } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAskQuestion, useDocuments, useInvestigation, useRuns } from '../api/hooks'
import type { ApiError } from '../api/types'
import { ContradictionList } from '../components/ContradictionList'
import { DocumentsPane } from '../components/DocumentsPane'
import { EvidencePane } from '../components/EvidencePane'
import { HistoryList } from '../components/HistoryList'
import { QuestionBar } from '../components/QuestionBar'
import { RunCard } from '../components/RunCard'
import { contradictionsOf, plural } from '../lib/format'

type Tab = 'questions' | 'contradictions'

const DISCOVERIES = [
  { Icon: BadgeCheck, text: 'Verified answers' },
  { Icon: FileText, text: 'Source evidence' },
  { Icon: GitCompare, text: 'Conflicting information' },
  { Icon: ShieldAlert, text: 'Gaps where the documents do not say' },
]

/** Keyed by investigation so that opening another case always starts with a clean workspace. */
export function WorkspacePage() {
  const { investigationId = '' } = useParams()
  return <Workspace key={investigationId} investigationId={investigationId} />
}

function Workspace({ investigationId }: { investigationId: string }) {
  const investigation = useInvestigation(investigationId)
  const documents = useDocuments(investigationId)
  const runs = useRuns(investigationId)
  const ask = useAskQuestion(investigationId)
  // Only questions asked since this workspace was opened are part of the active investigation.
  // Stored history stays in the database and is shown only on request.
  const [sessionRunIds, setSessionRunIds] = useState<string[]>([])
  const [repeatedRunId, setRepeatedRunId] = useState<string | null>(null)
  const [showEarlier, setShowEarlier] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('questions')
  const scroller = useRef<HTMLDivElement>(null)

  const allRuns = useMemo(() => runs.data ?? [], [runs.data])
  const visibleRuns = useMemo(() => {
    if (showEarlier) return allRuns
    const byId = new Map(allRuns.map((r) => [r.run_id, r]))
    return sessionRunIds.map((id) => byId.get(id)).filter((r) => r !== undefined)
  }, [allRuns, sessionRunIds, showEarlier])
  const earlierCount = allRuns.filter((r) => !sessionRunIds.includes(r.run_id)).length
  const contradictions = useMemo(() => contradictionsOf(visibleRuns), [visibleRuns])
  const selectedRun = visibleRuns.find((r) => r.run_id === selectedRunId) ?? visibleRuns[visibleRuns.length - 1] ?? null
  const activeRun = ask.isPending ? null : selectedRun
  const readyDocuments = documents.data?.filter((d) => d.status === 'ready').length ?? 0
  const activeTab: Tab = contradictions.length > 0 ? tab : 'questions'

  // a new question or selection brings the top of the result back into view
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 })
  }, [ask.isPending, selectedRun?.run_id])

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
    setSelectedClaimId(null)
    ask.mutate(question, {
      onSuccess: (run) => {
        setRepeatedRunId(sessionRunIds.includes(run.run_id) ? run.run_id : null)
        setSessionRunIds((ids) => (ids.includes(run.run_id) ? ids : [...ids, run.run_id]))
        setSelectedRunId(run.run_id)
      },
    })
  }

  const tabClass = (name: Tab) =>
    `border-b-2 px-1 pb-2 text-sm font-semibold ${
      activeTab === name ? 'border-ink text-ink' : 'border-transparent text-ink-soft hover:text-ink'
    }`
  const metric = 'inline-flex items-center gap-1.5 rounded-md border border-line bg-paper px-2.5 py-1.5 text-xs font-medium'

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between gap-4 border-b border-line bg-white px-5 py-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-accent">Document Investigator</p>
          <h1 className="truncate font-serif text-2xl leading-tight" data-testid="investigation-title">
            {investigation.data?.title ?? 'Loading…'}
          </h1>
        </div>
        <div className="flex shrink-0 items-center gap-2" data-testid="metrics">
          <span className={metric}>
            <FileText size={13} aria-hidden /> {plural(documents.data?.length ?? 0, 'document')}
          </span>
          {visibleRuns.length === 0 ? (
            <span className={`${metric} text-ink-soft`}>
              {readyDocuments > 0 ? 'Ready to investigate' : 'Waiting for documents'}
            </span>
          ) : (
            <span className={metric}>
              <MessageSquareText size={13} aria-hidden /> {plural(visibleRuns.length, 'question')}
            </span>
          )}
          {contradictions.length > 0 && (
            <button
              type="button"
              data-testid="conflict-metric"
              onClick={() => setTab('contradictions')}
              title="Show the conflicts found so far"
              className="inline-flex items-center gap-1.5 rounded-md border border-red-300 bg-red-50 px-2.5 py-1.5 text-xs font-semibold text-red-900 hover:border-red-500"
            >
              <GitCompare size={13} aria-hidden /> {plural(contradictions.length, 'conflict')} detected
            </button>
          )}
          {earlierCount > 0 && (
            <button
              type="button"
              data-testid="history-toggle"
              aria-pressed={showEarlier}
              onClick={() => {
                setShowEarlier(!showEarlier)
                setSelectedClaimId(null)
              }}
              title="Questions asked in this case before this session"
              className="rounded-md border border-line px-2.5 py-1.5 text-xs font-medium text-ink-soft hover:border-accent"
            >
              {showEarlier ? 'Hide earlier questions' : 'History'}
            </button>
          )}
          <Link
            to="/"
            className="ml-2 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold hover:border-accent"
          >
            Switch case
          </Link>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[272px_minmax(0,1fr)_392px] max-[1100px]:grid-cols-[240px_minmax(0,1fr)] max-[1100px]:grid-rows-[minmax(0,1fr)_minmax(0,40%)]">
        <aside className="min-h-0 border-r border-line bg-white p-4 max-[1100px]:row-span-2">
          <DocumentsPane investigationId={investigationId} />
        </aside>

        <section className="flex min-h-0 flex-col">
          <div className="flex gap-5 border-b border-line bg-white px-5 pt-3" role="tablist">
            <button type="button" role="tab" aria-selected={activeTab === 'questions'} className={tabClass('questions')} onClick={() => setTab('questions')}>
              Investigation
            </button>
            {contradictions.length > 0 && (
              <button
                type="button"
                role="tab"
                data-testid="tab-contradictions"
                aria-selected={activeTab === 'contradictions'}
                className={tabClass('contradictions')}
                onClick={() => setTab('contradictions')}
              >
                Contradictions found ({contradictions.length})
              </button>
            )}
          </div>

          <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {activeTab === 'contradictions' && <ContradictionList contradictions={contradictions} onOpen={selectRun} />}

            {activeTab === 'questions' && (
              <div className="space-y-4">
                {visibleRuns.length === 0 && !ask.isPending && (
                  <div data-testid="empty-investigation" className="mx-auto mt-10 max-w-md text-center">
                    {readyDocuments > 0 ? (
                      <>
                        <h2 className="font-serif text-3xl">Ready to investigate</h2>
                        <p className="mt-2 text-sm text-ink-soft">
                          Ask a question about {readyDocuments === 1 ? 'this document' : `these ${readyDocuments} documents`} to
                          uncover:
                        </p>
                        <ul className="mx-auto mt-4 inline-block space-y-2 text-left text-sm">
                          {DISCOVERIES.map(({ Icon, text }) => (
                            <li key={text} className="flex items-center gap-2">
                              <Icon size={16} className="text-accent" aria-hidden /> {text}
                            </li>
                          ))}
                        </ul>
                        <p className="mt-6 text-sm font-medium">Ask your first question below.</p>
                      </>
                    ) : (
                      <>
                        <h2 className="font-serif text-3xl">Add documents to begin</h2>
                        <p className="mt-2 text-sm text-ink-soft">
                          {documents.isLoading
                            ? 'Loading the documents for this case…'
                            : 'Add documents on the left. You can ask a question as soon as one is ready.'}
                        </p>
                      </>
                    )}
                  </div>
                )}

                {visibleRuns.length > 1 && (
                  <HistoryList runs={visibleRuns} selectedRunId={activeRun?.run_id ?? null} onSelect={selectRun} />
                )}

                {ask.isPending && (
                  <div data-testid="pending" className="rounded-lg border border-t-4 border-slate-300 bg-white p-6">
                    <p className="text-lg font-semibold">{ask.variables}</p>
                    <p className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
                      <LoaderCircle size={16} className="animate-spin" aria-hidden />
                      Retrieving evidence, checking quotes and comparing documents…
                    </p>
                  </div>
                )}
                {activeRun && (
                  <RunCard
                    key={activeRun.run_id}
                    run={activeRun}
                    repeated={activeRun.run_id === repeatedRunId}
                    selectedClaimId={selectedClaimId}
                    onSelectClaim={setSelectedClaimId}
                  />
                )}

                {ask.isError && (
                  <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">
                    The question could not be investigated: {(ask.error as unknown as ApiError).message}
                  </p>
                )}
              </div>
            )}
          </div>

          <QuestionBar readyDocuments={readyDocuments} pending={ask.isPending} onAsk={onAsk} />
        </section>

        <aside className="min-h-0 border-l border-line p-4 max-[1100px]:border-l-0 max-[1100px]:border-t">
          {/* keyed by the selected question so page-viewer and card state never carry over */}
          <EvidencePane
            key={activeRun?.run_id ?? 'none'}
            run={activeRun}
            pending={ask.isPending}
            selectedClaimId={selectedClaimId}
            onSelectClaim={setSelectedClaimId}
          />
        </aside>
      </div>
    </div>
  )
}
