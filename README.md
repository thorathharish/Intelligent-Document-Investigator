# Document Investigator

ALGOTHON'26 · ALG-AI-02 Intelligent Document Investigator

An AI document investigator that answers questions from your documents using verified source evidence,
detects conflicting information, and says when the evidence is insufficient.

## The problem

Information is scattered across PDFs, Word files, text files and scanned images. People need answers
without reading everything, but a plain "chat with your documents" tool will confidently return one
answer even when the documents disagree or do not contain the answer at all.

## The solution

Document Investigator treats retrieved text as **evidence**, not just context:

> The language model interprets evidence. The application verifies evidence. Fixed rules evaluate
> conflicts and uncertainty. The final answer is built only from verified evidence.

For every question it runs: **ask → retrieve → analyse → verify → compare → rate → answer with sources**.

## Main features

- **Verified citations.** Every quote is checked against the stored document text before it is shown.
  Document names, pages and sections come from the database, never from the model.
- **Conflict detection.** When documents state different values for the same fact (for example 30 days
  versus 45 days), both positions are shown with their sources. No side is chosen automatically. If a
  document says it replaces another, that is shown as a cited note beside the conflict.
- **Evidence state.** Each answer is rated HIGH, MEDIUM, LOW, CONFLICT or INSUFFICIENT by fixed rules
  over the checked evidence, with plain-language reasons. There are no confidence percentages.
- **Cross-document answers.** One question can draw on several documents, each cited separately.
- **Multiple formats.** PDF, DOCX, TXT, PNG and JPG. Scanned images and scanned PDF pages are read with
  local OCR and marked as scanned.
- **Investigation workspace.** Documents, the answer and its verified evidence side by side, with a page
  viewer that highlights the quote on the original page.
- **Graceful failure.** If the model is unavailable the app shows the closest passages as evidence
  instead of failing or guessing.

## Architecture

```text
React + Vite frontend  ──HTTPS──►  FastAPI backend (single process)
                                     ├─ Ingestion: validate → extract → OCR → clean → chunk → embed
                                     ├─ Retrieval: BM25 + dense embeddings, rank fusion, one slot per document
                                     ├─ Evidence analyst: one model call per question (OpenRouter)
                                     ├─ Verifier: quote and value checks (code)
                                     ├─ Conflict engine (code)
                                     ├─ Uncertainty engine (code)
                                     └─ Answer composer (code)
                                   SQLite + local files
```

Design documents are in `docs/` (`HLD.md`, `LLD.md`, `PHASE5_PLAN.md`).

## Technology

| Layer | Used |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, lucide-react |
| Backend | Python 3.11, FastAPI, Uvicorn, Pydantic |
| Extraction | PyMuPDF, python-docx |
| OCR | rapidocr-onnxruntime (local) |
| Embeddings | fastembed with `BAAI/bge-small-en-v1.5` (local) |
| Keyword search | rank-bm25 |
| Matching | rapidfuzz |
| Storage | SQLite, local filesystem |
| Tests | pytest |

All of the above are open-source libraries.

## External services

- **OpenRouter** is the only external API. It is called once per new question, with the question and
  the retrieved passages, to extract claims and quotes. The key is held only by the backend.
- Embeddings and OCR run locally on the backend. The embedding model is downloaded from Hugging Face
  the first time it is used.

## Run locally

Requirements: Python 3.11, Node.js 20 or newer, an OpenRouter API key.

```powershell
# backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env      # then set OPENROUTER_API_KEY
uvicorn app.main:app --app-dir backend --port 8000

# frontend (second terminal)
npm --prefix frontend install
npm --prefix frontend run dev                    # http://localhost:5173
```

Tests and acceptance checks:

```powershell
python -m pytest backend\tests -q
python scripts\acceptance.py                     # needs the backend running
```

## Deployment

The backend and frontend are hosted separately.

**Backend (Oracle Cloud Always Free VM).** `deploy/oracle/` holds the setup script, the systemd service,
the Nginx site and step-by-step instructions (`deploy/oracle/README.md`).

- Runs as: systemd → Uvicorn (one worker) → FastAPI, behind Nginx on port 80
- Start: `uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1`
- Health check: `/api/health`
- Environment (in `/etc/document-investigator.env`): `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
  `OPENROUTER_FALLBACK_MODELS`, `LLM_MODE=live`, `DATA_DIR`, and `ALLOWED_ORIGINS` set to the
  frontend's origin

**Frontend (Vercel).** Root directory `frontend`, build `npm run build`, output `dist`.

- Environment: `VITE_API_BASE_URL` set to the backend's public URL (no secret belongs here)

## Try the demo

Two demo cases are bundled in `demo_docs/` and can be opened from the home page. All parties in them are
fictional and the documents were written for this project.

**Contract case** (services agreement, amendment, scanned invoice, payment policy):

| Question | Result |
|---|---|
| What is the late payment fee? | HIGH — 1.5% per month, two documents agree |
| What is the invoice total, and who has to approve it? | MEDIUM — two documents, one fact each |
| What payment terms apply? | CONFLICT — 30 days (agreement, amendment) versus 45 days (scanned invoice) |
| How much notice is needed to terminate the agreement? | CONFLICT — 60 versus 90 days, with a supersession note |
| What is the warranty period for the equipment? | INSUFFICIENT — the documents do not say |

**HR case** (handbook, offer letter, memo), an unrelated domain handled by the same code:

| Question | Result |
|---|---|
| How many days of annual leave do employees get? | CONFLICT — 18 versus 24 days |
| Is remote work permitted? | CONFLICT — yes versus no |
| How long is the probation period? | HIGH — 6 months |
| How much is the health insurance cover? | INSUFFICIENT |

## Known limitations

- Conflicts are detected between **comparable values on the same topic**: durations, numbers, money,
  percentages, dates, yes/no, and short text alternatives. Arbitrary logical contradictions are not detected.
- Grouping claims by topic depends on the model. If it files the same fact under two topics, a conflict can
  be missed. One demo question shows this: "What payment terms apply after the amendment, and does the
  invoice follow them?" returns MEDIUM with both terms cited, not CONFLICT.
- Unit equivalence is not inferred: "1 month" and "30 days" are treated as different values.
- Scanned pages have no text layer, so the page viewer shows them without a highlight.
- Storage is SQLite and local files. On a host with an ephemeral disk, investigations are lost when the
  service restarts and the demo cases must be loaded again.
- Free model tiers have request limits; when a model is unavailable the app falls back to evidence only.
- In the hosted demo, answers that are served from a stored result are shown after a short fixed-range
  wait so the interface does not jump; new questions are answered live with no added wait.
- There is no sign-in. Do not upload sensitive documents; passages are sent to a third-party model.

## AI tools and disclosure

- **In the product:** a language model reached through OpenRouter (`nvidia/nemotron-3-super-120b-a12b:free`
  with free fallback models) extracts claims and quotes from retrieved passages. It does not decide the
  evidence state, the conflicts or the citations; application code does.
- **In development:** this project was built with AI assistance. Claude Code (Anthropic) was used to
  design, write and test the code under the author's direction.
- **Data:** the demo documents are synthetic and were generated for this project. No third-party datasets
  are used.
