import { FileText, ScanLine, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useDocuments, useUploadDocuments } from '../api/hooks'
import type { ApiError, DocumentInfo, DocumentStatus } from '../api/types'
import { displayName, fileType, plural } from '../lib/format'

const STATUS: Record<DocumentStatus, { label: string; style: string }> = {
  queued: { label: 'Queued', style: 'bg-slate-100 text-slate-700' },
  extracting: { label: 'Reading', style: 'bg-sky-100 text-sky-900' },
  indexing: { label: 'Indexing', style: 'bg-sky-100 text-sky-900' },
  ready: { label: 'Ready', style: 'bg-emerald-100 text-emerald-900' },
  failed: { label: 'Failed', style: 'bg-red-100 text-red-900' },
  duplicate: { label: 'Duplicate', style: 'bg-amber-100 text-amber-900' },
}

function DocumentRow({ doc }: { doc: DocumentInfo }) {
  const scanned = doc.extraction_method === 'ocr' || doc.extraction_method === 'mixed'
  const details = [
    fileType(doc.filename),
    doc.page_count != null ? plural(doc.page_count, 'page') : null,
    doc.status === 'ready' ? plural(doc.chunk_count, 'passage') : null,
  ].filter(Boolean)

  return (
    <li data-testid="document" className="border-b border-line py-2.5">
      <div className="flex items-start gap-2">
        <FileText size={16} className="mt-0.5 shrink-0 text-ink-soft" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-snug" title={doc.filename}>
            {displayName(doc.filename)}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-ink-soft">
            <span>{details.join(' · ')}</span>
            {scanned && (
              <span className="inline-flex items-center gap-1 text-amber-800" title="Text was read from an image by OCR">
                <ScanLine size={12} aria-hidden /> Scanned
              </span>
            )}
          </p>
          {doc.status === 'failed' && (
            <p className="mt-1 text-xs text-red-800">{doc.error_message ?? 'This file could not be read.'}</p>
          )}
          {doc.status === 'duplicate' && (
            <p className="mt-1 text-xs text-amber-800">Same content as a file already in this investigation.</p>
          )}
        </div>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${STATUS[doc.status].style}`}>
          {STATUS[doc.status].label}
        </span>
      </div>
    </li>
  )
}

export function DocumentsPane({ investigationId }: { investigationId: string }) {
  const documents = useDocuments(investigationId)
  const upload = useUploadDocuments(investigationId)
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const send = (files: FileList | null) => {
    if (files && files.length > 0) upload.mutate(Array.from(files))
  }
  const list = documents.data ?? []
  const ready = list.filter((d) => d.status === 'ready').length

  return (
    <section className="flex h-full flex-col">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold">Documents</h2>
        {list.length > 0 && (
          <span className="text-xs text-ink-soft">
            {ready} of {list.length} ready
          </span>
        )}
      </div>

      <ul className="mt-1 min-h-0 flex-1 overflow-y-auto">
        {documents.isLoading && <li className="py-3 text-sm text-ink-soft">Loading documents…</li>}
        {documents.isError && <li className="py-3 text-sm text-red-800">The document list could not be loaded.</li>}
        {list.map((doc) => (
          <DocumentRow key={doc.id} doc={doc} />
        ))}
        {documents.isSuccess && list.length === 0 && (
          <li className="py-3 text-sm text-ink-soft">Add the documents you want to investigate.</li>
        )}
      </ul>

      {upload.isError && <p className="mb-2 text-xs text-red-800">{(upload.error as unknown as ApiError).message}</p>}
      {upload.data && upload.data.rejected.length > 0 && (
        <ul className="mb-2 text-xs text-red-800">
          {upload.data.rejected.map((r, i) => (
            <li key={i}>
              {r.filename}: {r.reason}
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          send(e.dataTransfer.files)
        }}
        onClick={() => input.current?.click()}
        className={`mt-2 rounded-lg border border-dashed px-3 py-3 text-center text-sm transition-colors ${
          dragging ? 'border-accent bg-blue-50' : 'border-slate-300 bg-white hover:border-accent'
        }`}
      >
        <span className="inline-flex items-center gap-2 font-medium">
          <Upload size={15} aria-hidden />
          {upload.isPending ? 'Uploading…' : 'Add documents'}
        </span>
        <span className="mt-0.5 block text-xs text-ink-soft">PDF, Word, text or scanned images</span>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
        className="hidden"
        onChange={(e) => {
          send(e.target.files)
          e.target.value = ''
        }}
      />
    </section>
  )
}
