import { Search } from 'lucide-react'
import { useState } from 'react'
import { plural } from '../lib/format'

interface Props {
  readyDocuments: number
  pending: boolean
  onAsk: (question: string) => void
}

export function QuestionBar({ readyDocuments, pending, onAsk }: Props) {
  const [question, setQuestion] = useState('')
  const disabled = readyDocuments === 0

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const text = question.trim()
    if (!text || disabled || pending) return
    onAsk(text)
    setQuestion('')
  }

  return (
    <form onSubmit={submit} className="border-t border-line bg-white px-5 pb-3 pt-3.5">
      <div className="flex gap-2">
        <label className="relative flex-1">
          <span className="sr-only">Question</span>
          <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-soft" aria-hidden />
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={disabled || pending}
            maxLength={500}
            placeholder={disabled ? 'Add a document to begin' : 'Ask a question about these documents'}
            className="h-12 w-full rounded-lg border border-slate-400 pl-11 pr-3 text-base shadow-sm placeholder:text-slate-400 focus:border-accent disabled:bg-slate-100"
          />
        </label>
        <button
          type="submit"
          disabled={disabled || pending || !question.trim()}
          className="h-12 rounded-lg bg-ink px-6 text-sm font-semibold text-white hover:bg-accent disabled:opacity-40"
        >
          {pending ? 'Investigating…' : 'Investigate'}
        </button>
      </div>
      <p className="mt-1.5 pl-1 text-xs text-ink-soft" data-testid="question-hint">
        {disabled
          ? 'Questions can be asked as soon as one document is ready.'
          : `Searches across ${readyDocuments === 1 ? 'the 1 ready document' : `all ${plural(readyDocuments, 'ready document')}`}. Every answer is checked against the source text.`}
      </p>
    </form>
  )
}
