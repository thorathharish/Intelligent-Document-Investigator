import { useRef, useState } from 'react'
import { useDocuments, useUploadDocuments } from '../api/hooks'
import type { ApiError, DocumentInfo, DocumentStatus } from '../api/types'

const STATUS_LABEL: Record<DocumentStatus, string> = {
  queued: 'Queued',
  extracting: 'Extracting',
  indexing: 'Indexing',
  ready: 'Ready',
  failed: 'Failed',
  duplicate: 'Duplicate',
}

const STATUS_STYLE: Record<DocumentStatus, string> = {
  queued: 'bg-slate-100 text-slate-700',
  extracting: 'bg-blue-100 text-blue-800',
  indexing: 'bg-blue-100 text-blue-800',
  ready: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  duplicate: 'bg-amber-100 text-amber-800',
}

function DocumentRow({ doc }: { doc: DocumentInfo }) {
  return (
    <li className="border-b border-slate-200 py-2 text-sm">
      <div className="flex items-start justify-between gap-2">
        <span className="break-all font-medium">{doc.filename}</span>
        <span className={`shrink-0 rounded px-2 py-0.5 text-xs ${STATUS_STYLE[doc.status]}`}>
          {STATUS_LABEL[doc.status]}
        </span>
      </div>
      <div className="mt-0.5 text-xs text-slate-500">
        {doc.page_count != null && `${doc.page_count} page${doc.page_count === 1 ? '' : 's'} · `}
        {doc.status === 'ready' && `${doc.chunk_count} passages`}
        {(doc.extraction_method === 'ocr' || doc.extraction_method === 'mixed') && ' · scan'}
      </div>
      {doc.error_message && <div className="mt-0.5 text-xs text-red-700">{doc.error_message}</div>}
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

  return (
    <section className="flex h-full flex-col">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Documents</h2>

      <div
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
        className={`mt-2 cursor-pointer rounded border-2 border-dashed p-4 text-center text-sm ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white'
        }`}
      >
        {upload.isPending ? 'Uploading…' : 'Drop files here or click to choose'}
        <div className="mt-1 text-xs text-slate-500">PDF, DOCX, TXT, PNG, JPG · up to 10 files, 20 MB each</div>
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
      </div>

      {upload.isError && (
        <p className="mt-2 text-xs text-red-700">{(upload.error as unknown as ApiError).message}</p>
      )}
      {upload.data && upload.data.rejected.length > 0 && (
        <ul className="mt-2 text-xs text-red-700">
          {upload.data.rejected.map((r, i) => (
            <li key={i}>
              {r.filename}: {r.reason}
            </li>
          ))}
        </ul>
      )}

      <ul className="mt-3 flex-1 overflow-y-auto">
        {documents.data?.map((doc) => <DocumentRow key={doc.id} doc={doc} />)}
        {documents.data?.length === 0 && <li className="py-2 text-sm text-slate-500">No documents yet.</li>}
      </ul>
    </section>
  )
}
