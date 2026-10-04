import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAskQuestion, useDocuments, useInvestigation, useRuns } from '../api/hooks'
import type { ApiError } from '../api/types'
import { DocumentsPane } from '../components/DocumentsPane'
import { EvidencePane } from '../components/EvidencePane'
import { QuestionBar } from '../components/QuestionBar'
import { RunCard } from '../components/RunCard'

export function WorkspacePage() {
  const { investigationId = '' } = useParams()
  const investigation = useInvestigation(investigationId)
  const documents = useDocuments(investigationId)
  const runs = useRuns(investigationId)
  const ask = useAskQuestion(investigationId)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null)

  if (investigation.isError) {
    return (
      <main className="p-8">
        <p className="text-sm text-red-700">Investigation not found.</p>
        <Link to="/" className="text-sm underline">
          Back to start
        </Link>
      </main>
    )
  }

  const allRuns = runs.data ?? []
  const selectedRun = allRuns.find((r) => r.run_id === selectedRunId) ?? allRuns[allRuns.length - 1] ?? null
  const hasReadyDocument = documents.data?.some((d) => d.status === 'ready') ?? false

  const onAsk = (question: string) => {
    ask.mutate(question, {
      onSuccess: (run) => {
        setSelectedRunId(run.run_id)
        setSelectedClaimId(null)
      },
    })
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <Link to="/" className="text-xs text-slate-500">
          Document Investigator
        </Link>
        <h1 className="text-lg font-semibold">{investigation.data?.title ?? '…'}</h1>
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr_380px]">
        <aside className="min-h-0 border-r border-slate-200 p-3">
          <DocumentsPane investigationId={investigationId} />
        </aside>

        <section className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Investigation</h2>
            {allRuns.length === 0 && !ask.isPending && (
              <p className="text-sm text-slate-500">Questions and their evidence-backed answers appear here.</p>
            )}
            {allRuns.map((run) => (
              <RunCard
                key={run.run_id}
                run={run}
                selected={run.run_id === selectedRun?.run_id}
                selectedClaimId={selectedClaimId}
                onSelect={() => {
                  if (run.run_id !== selectedRun?.run_id) setSelectedClaimId(null)
                  setSelectedRunId(run.run_id)
                }}
                onSelectClaim={setSelectedClaimId}
              />
            ))}
            {ask.isPending && (
              <div data-testid="pending" className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-600">
                <p className="font-medium">{ask.variables}</p>
                <p className="mt-1 animate-pulse">
                  Retrieving evidence · Analysing passages · Verifying quotes
                </p>
              </div>
            )}
            {ask.isError && (
              <p className="text-sm text-red-700">{(ask.error as unknown as ApiError).message}</p>
            )}
          </div>
          <QuestionBar disabled={!hasReadyDocument} pending={ask.isPending} onAsk={onAsk} />
        </section>

        <aside className="min-h-0 border-l border-slate-200 p-3">
          <EvidencePane run={selectedRun} selectedClaimId={selectedClaimId} />
        </aside>
      </div>
    </div>
  )
}
