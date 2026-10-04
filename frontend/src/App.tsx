import { useEffect, useState } from 'react'

type Health = { ok: boolean; llm_mode: string; model: string; embedder: string; ocr: string }

// Checkpoint 1 scaffold: proves the SPA loads and can reach the API through the proxy.
function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main className="min-h-screen bg-slate-50 p-8 text-slate-900">
      <h1 className="text-2xl font-semibold">Document Investigator</h1>
      <p className="mt-2 text-sm text-slate-600">
        {health && `API ok · mode ${health.llm_mode} · model ${health.model}`}
        {error && `API unreachable: ${error}`}
        {!health && !error && 'Checking API…'}
      </p>
    </main>
  )
}

export default App
