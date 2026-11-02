import { useEffect, useState, type FormEvent } from 'react'
import './App.css'

type QuestionResult = {
  question: string
  answer: string
  status: string
  evidence: string[]
}

const defaultQuestion = 'What is the current normal operating pressure for the HPU, and under what conditions does that apply?'

function App() {
  const [question, setQuestion] = useState(defaultQuestion)
  const [result, setResult] = useState<QuestionResult | null>(null)
  const [evaluation, setEvaluation] = useState<QuestionResult[]>([])
  const [documentCount, setDocumentCount] = useState(0)
  const [error, setError] = useState('')

  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  useEffect(() => {
    fetch(`${apiBase}/api/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_path: './aegis-dataset' }),
    })
      .then((response) => response.json())
      .then((payload) => {
        const items = Array.isArray(payload.evaluation_questions) ? payload.evaluation_questions : []
        setEvaluation(items)
        setDocumentCount(Number(payload.documents) || 0)
        if (items.length > 0) {
          setQuestion(items[1]?.question || items[0]?.question || defaultQuestion)
          setResult(items[1] || items[0] || null)
        }
      })
      .catch(() => {
        setError('The backend is not running yet. Start the API on port 8000 to enable ingestion.')
      })
  }, [apiBase])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const response = await fetch(`${apiBase}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const payload = await response.json()
      setResult(payload)
    } catch {
      setError('Unable to reach the backend. Please start the FastAPI server first.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">Aegis Series-7</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">Knowledge Ingestion Console</h1>
          </div>
          <div className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
            {documentCount} source documents indexed
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-8 px-6 py-8 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/50">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Evidence-grounded Q&A</h2>
            <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-xs uppercase tracking-[0.2em] text-cyan-300">
              live
            </span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={5}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none ring-0 transition focus:border-cyan-500"
              placeholder="Ask a question about HPU pressure, alarms, sensor aliases, or revisions..."
            />
            <div className="flex items-center justify-between gap-3">
              <button
                type="submit"
                className="rounded-xl bg-cyan-500 px-5 py-2.5 font-medium text-slate-950 transition hover:bg-cyan-400"
              >
                Submit question
              </button>
              <span className="text-xs text-slate-400">Answer status is measured against source provenance</span>
            </div>
          </form>

          {error ? <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div> : null}

          {result ? (
            <article className="mt-6 rounded-2xl border border-slate-700 bg-slate-950/70 p-5">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="text-sm font-medium uppercase tracking-[0.18em] text-slate-400">Result</h3>
                <span className={`status-pill status-pill--${result.status.replace(/_/g, '-')}`}>{result.status}</span>
              </div>
              <p className="text-lg leading-8 text-slate-100">{result.answer}</p>
              <div className="mt-5 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Evidence</p>
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
                  {result.evidence?.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </article>
          ) : null}
        </section>

        <aside className="space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <h3 className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Evaluation questions</h3>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              {evaluation.slice(0, 8).map((item) => (
                <li key={item.question}>
                  <button
                    type="button"
                    onClick={() => {
                      setQuestion(item.question)
                      setResult(item)
                    }}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-left transition hover:border-cyan-500 hover:text-cyan-200"
                  >
                    {item.question}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <h3 className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">System notes</h3>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              <li>Authoritative manuals outrank legacy or informal field notes.</li>
              <li>Conflicting facts are preserved and labeled as version-dependent.</li>
              <li>Unverified claims are reported as “cannot_determine” rather than invented.</li>
            </ul>
          </div>
        </aside>
      </main>
    </div>
  )
}

export default App
