import { Link, useParams } from 'react-router-dom'
import { useInvestigation } from '../api/hooks'
import { DocumentsPane } from '../components/DocumentsPane'

export function WorkspacePage() {
  const { investigationId = '' } = useParams()
  const investigation = useInvestigation(investigationId)

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
        <section className="min-h-0 p-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Investigation</h2>
        </section>
        <aside className="min-h-0 border-l border-slate-200 p-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Evidence</h2>
        </aside>
      </div>
    </div>
  )
}
