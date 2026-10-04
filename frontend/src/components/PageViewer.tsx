import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Evidence } from '../api/types'
import { locationOf } from '../lib/format'

/** The source page as stored, with the verified quote highlighted when the page has a text layer. */
export function PageViewer({ evidence, onClose }: { evidence: Evidence; onClose: () => void }) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const src =
    `/api/documents/${evidence.document_id}/pages/${evidence.page}/image` +
    (evidence.extraction_method === 'text' ? `?q=${encodeURIComponent(evidence.quote)}` : '')

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${evidence.document}, ${locationOf(evidence)}`}
      data-testid="page-viewer"
      onClick={onClose}
      className="fixed inset-0 z-20 flex items-center justify-center bg-ink/60 p-6"
    >
      <div onClick={(e) => e.stopPropagation()} className="flex max-h-full w-full max-w-3xl flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{evidence.document}</p>
            <p className="text-xs text-ink-soft">
              {locationOf(evidence)}
              {evidence.extraction_method === 'ocr' ? ', scanned image' : ', verified quote highlighted'}
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-paper">
            <X size={18} />
          </button>
        </div>
        <div className="min-h-[240px] overflow-auto bg-paper p-4">
          {status === 'loading' && <p className="text-sm text-ink-soft">Loading the page…</p>}
          {status === 'error' && <p className="text-sm text-red-800">This page could not be displayed.</p>}
          <img
            src={src}
            alt={`Page ${evidence.page} of ${evidence.document}`}
            data-testid="page-image"
            onLoad={() => setStatus('ready')}
            onError={() => setStatus('error')}
            className={`mx-auto border border-line bg-white ${status === 'ready' ? '' : 'hidden'}`}
          />
        </div>
      </div>
    </div>
  )
}
