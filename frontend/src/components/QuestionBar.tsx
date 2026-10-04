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
    <form onSubmit={submit} className="flex gap-2 border-t border-slate-200 bg-white p-3">
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        disabled={disabled || pending}
        maxLength={500}
        placeholder={disabled ? 'Upload a document to begin' : 'Ask a question about these documents…'}
        className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
      />
      <button
        type="submit"
        disabled={disabled || pending || !question.trim()}
        className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {pending ? 'Investigating…' : 'Ask'}
      </button>
    </form>
  )
}
