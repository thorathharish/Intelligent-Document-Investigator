import { Search } from 'lucide-react'
import { useState } from 'react'

interface Props {
  disabled: boolean
  pending: boolean
  onAsk: (question: string) => void
}

export function QuestionBar({ disabled, pending, onAsk }: Props) {
  const [question, setQuestion] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const text = question.trim()
    if (!text || disabled || pending) return
    onAsk(text)
    setQuestion('')
  }

  return (
    <form onSubmit={submit} className="flex gap-2 border-t border-line bg-white px-5 py-3">
      <label className="relative flex-1">
        <span className="sr-only">Question</span>
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft" aria-hidden />
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={disabled || pending}
          maxLength={500}
          placeholder={disabled ? 'Add a document to begin' : 'Ask a question about these documents'}
          className="w-full rounded-lg border border-slate-300 py-2.5 pl-9 pr-3 text-sm disabled:bg-slate-100"
        />
      </label>
      <button
        type="submit"
        disabled={disabled || pending || !question.trim()}
        className="rounded-lg bg-ink px-5 py-2.5 text-sm font-medium text-white hover:bg-accent disabled:opacity-40"
      >
        {pending ? 'Investigating…' : 'Investigate'}
      </button>
    </form>
  )
}
