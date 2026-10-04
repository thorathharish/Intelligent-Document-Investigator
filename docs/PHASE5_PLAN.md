# PHASE 5 — IMPLEMENTATION & EXECUTION PLAN

ALG-AI-02 Intelligent Document Investigator · solo developer · 12 hours · OpenRouter free model.
Sources of truth: frozen HLD (kept as the appendix at the bottom of this file) and frozen LLD (`D:\Algothon\docs\LLD.md`). "LLD §n" below refers to that file.

## 1. PHASE 5 PURPOSE

- **Does:** turns the LLD into an ordered build: which file, in which checkpoint, with which command, test, done-criterion and fallback.
- **Does not:** change architecture, schemas, API, prompt, or rules; write application code.
- **Link to LLD:** every task names the LLD section it implements. If a task and the LLD disagree, the LLD wins.

**Reconciliations found while planning** (none changes HLD/LLD design):

| # | Item | Smallest correction | HLD/LLD update needed |
|---|---|---|---|
| 1 | Your checkpoint list numbers OCR as 6, Set B as 7, UI as 8, deploy as 9, freeze/rehearsal as 10. The HLD used the same times but numbered Set B 6, UI 7, deploy 8, freeze 9, rehearsal 10 | This plan uses **your numbering**. The HLD gates become: P1 starts only after Checkpoint 7 is closed; P2 only after Checkpoint 9 | No (labels only) |
| 2 | Conflict work (Checkpoint 4) needs the invoice's "45 days", but the invoice is a scan and OCR arrives at Checkpoint 6 | `make_demo_docs.py` emits the invoice as both a text PDF and a PNG. The PDF is used until Checkpoint 6, then the PNG replaces it. This is the LLD's own OCR cut rule, used early | No |
| 3 | LLD demo question A2 (cross-document) returns CONFLICT, so the demo would show conflict twice and never a clean multi-document answer | Add one validation/demo question **A7**: "What is the invoice total, and who has to approve it?" → MEDIUM, cites Invoice + Policy. It lives only in this plan and in `acceptance.py`. Nothing is tuned to make it pass; if it does not behave, the demo uses A2 instead | No (LLD untouched) |
| 4 | You require tests for LLM timeout / 429 / invalid JSON; LLD §20.1 lists four unit-test files | Add `backend/tests/test_llm.py` using a fake HTTP transport. The adapter takes an optional HTTP client for this | No |
| 5 | The vertical slice at 13:30 must "determine state", but the rule table is Checkpoint 5 | At Checkpoint 3 the state is provisional: INSUFFICIENT if no verified claims, otherwise MEDIUM. Replaced at Checkpoint 5 | No |
| 6 | "Discord requirement" is in your checklist; I do not know the event's rule | Kept as a checklist item; you fill in the specifics | No |
| 7 | HLD §21 and §38 mention a spare API key as insurance | **Not used.** This plan has one key and no key rotation. The HLD text stays as written; this plan overrides that advisory line | No |
| 8 | Order of the LLM failure chain | Fixed for implementation as: primary model → retry primary once → fallback model(s) → recorded run if one exists → evidence-only. This is HLD §27's order; the recorder is consulted after network failure in any mode | No |

**Frozen for Phase 6:** the HLD, the LLD and this plan's execution architecture are immutable. Problems are solved inside the existing design with the smallest change. A genuine architectural blocker is reported, not redesigned around (§19).

If the day starts late, keep the order and apply the cut rules in §16 by time remaining.

## 2. FINAL IMPLEMENTATION SCOPE

**P0 — MUST WORK**
- Investigation creation and return by URL
- Multi-document upload with per-document status and per-file rejection
- PDF, TXT, DOCX, PNG/JPG handling (LLD §7)
- Extraction with page / section / paragraph metadata
- Local OCR (rapidocr) for images and text-less PDF pages
- Cleaning, page-bounded chunking
- Local embeddings (fastembed), BM25, hybrid fusion, per-document diversity
- Question answering through **one** LLM analyst call
- Quote verification, typed value verification, DB-sourced citations
- Cross-document reasoning (aspects)
- Deterministic conflict detection and uncertainty state
- Evidence-only fallback, LLM failure handling, replay/mock modes, run cache
- Demo Set A and unrelated Set B, both seedable
- Basic three-column UI: documents, answer + state + citations, evidence list
- Unit tests, acceptance script A–H, README, rehearsed demo

**P1 — SHOULD WORK**
- Polished evidence panel grouped by position, citation ↔ card linking
- Why This Answer panel
- Contradiction map
- Investigation history (collapsible run list)
- Page viewer with highlighted quote
- Visual polish

**P2 — ONLY IF TIME**
- Timeline, document relationship graph
- Extra visual polish / animation
- LLM vision OCR fallback
- Hosted deployment

**P2 must never delay P0.** P1 does not start until Checkpoint 7 is closed (Set A acceptance green, Set B validated and any out-of-scope gap documented).

Priority order inside P0: **Set A working → core acceptance tests passing → Set B generalisation validation.**

## 3. REPOSITORY / FILE CREATION PLAN

```text
D:\Algothon
├─ .gitignore
├─ README.md
├─ backend/
│  ├─ requirements.txt
│  ├─ .env.example            (.env is local, git-ignored)
│  ├─ app/
│  │  ├─ __init__.py  main.py  config.py  db.py  schemas.py  logging_utils.py
│  │  ├─ api/            __init__.py investigations.py documents.py questions.py evidence.py demo.py
│  │  ├─ ingestion/      __init__.py validate.py extract.py ocr.py clean.py chunk.py pipeline.py
│  │  ├─ retrieval/      __init__.py embedder.py index.py retriever.py
│  │  ├─ investigation/  __init__.py prompts.py analyst.py verifier.py normalize.py conflicts.py uncertainty.py composer.py orchestrator.py
│  │  └─ llm/            __init__.py base.py json_utils.py recorder.py openrouter.py
│  └─ tests/             test_normalize.py test_verifier.py test_conflicts.py test_uncertainty.py test_llm.py
├─ frontend/
│  ├─ vite.config.ts  index.html  package.json
│  └─ src/
│     ├─ main.tsx  App.tsx  index.css
│     ├─ api/         client.ts  types.ts  hooks.ts
│     ├─ pages/       HomePage.tsx  WorkspacePage.tsx
│     └─ components/  DocumentsPane.tsx  QuestionBar.tsx  RunCard.tsx  StateBadge.tsx
│                     EvidencePane.tsx  ContradictionMap.tsx  WhyThisAnswer.tsx  PageViewer.tsx
├─ scripts/           llm_smoke.py  make_demo_docs.py  acceptance.py
├─ demo_docs/         set_a/  set_b/      (generated, committed)
├─ data/              app.db  uploads/  llm_recordings/   (git-ignored)
└─ docs/              HLD.md  LLD.md  PHASE5_PLAN.md
```

| Order | Path | Purpose | Depends on | CP |
|---|---|---|---|---|
| 1 | `.gitignore`, `docs/HLD.md`, `docs/PHASE5_PLAN.md` | Ignore `.venv`, `node_modules`, `data/`, `.env`, `dist`; copy this file's appendix and plan into the repo | — | 1 |
| 2 | `backend/requirements.txt` | LLD §2 list | — | 1 |
| 3 | `backend/.env.example`, `backend/.env` | LLD §3 keys | — | 1 |
| 4 | `backend/app/config.py` | Settings, repo-root-relative paths | 3 | 1 |
| 5 | `backend/app/logging_utils.py` | `key=value` stage logger (LLD §17) | — | 1 |
| 6 | `backend/app/db.py` | Per-thread connection, WAL, schema bootstrap (LLD §4) | 4 | 1 |
| 7 | `backend/app/schemas.py` | Request/response + analyst output models; grows each checkpoint | — | 1 |
| 8 | `backend/app/main.py` | App, routers, error shape, later SPA mount | 4–7 | 1 |
| 9 | `backend/app/api/demo.py` | `/health` now, `/demo/seed` at CP7 | 8 | 1, 7 |
| 10 | `backend/app/llm/base.py` | `LLMClient`, `LLMResult`, error types | — | 1 |
| 11 | `backend/app/llm/json_utils.py` | Tolerant JSON extraction | — | 1 |
| 12 | `backend/app/llm/recorder.py` | live / replay / mock store | 4 | 1 |
| 13 | `backend/app/llm/openrouter.py` | HTTP call, retry, fallback, repair | 10–12 | 1 |
| 14 | `backend/app/investigation/prompts.py` | System prompt v1 + user template (LLD §10) | — | 1 |
| 15 | `scripts/llm_smoke.py` | Run the analyst prompt on a pasted sample against candidate models | 13, 14 | 1 |
| 16 | `frontend/` scaffold, `vite.config.ts`, `index.css` | Vite + React + TS + Tailwind, `/api` proxy to :8000 | — | 1 |
| 17 | `backend/app/ingestion/validate.py` | LLD §7.1 | 6 | 2 |
| 18 | `backend/app/ingestion/extract.py` | PDF, DOCX, TXT; headings (LLD §7.2) | — | 2 |
| 19 | `backend/app/ingestion/clean.py` | LLD §7.4 | — | 2 |
| 20 | `backend/app/ingestion/chunk.py` | LLD §7.5 | 18, 19 | 2 |
| 21 | `backend/app/retrieval/embedder.py` | fastembed singleton | 4 | 2 |
| 22 | `backend/app/ingestion/pipeline.py` | `process_document` (LLD §7.6) | 17–21 | 2 |
| 23 | `backend/app/api/investigations.py` | Create / get | 6, 7 | 2 |
| 24 | `backend/app/api/documents.py` | Upload / list | 22 | 2 |
| 25 | `scripts/make_demo_docs.py` | Set A (invoice as PDF and PNG) | — | 2 |
| 26 | `frontend/src/api/{client,types,hooks}.ts` | Fetch wrapper, types, queries | 16 | 2 |
| 27 | `frontend/src/App.tsx`, `pages/HomePage.tsx`, `pages/WorkspacePage.tsx`, `components/DocumentsPane.tsx` | Routes, create, upload, status | 26 | 2 |
| 28 | `backend/app/retrieval/index.py` | In-memory matrix + BM25 per investigation | 21 | 3 |
| 29 | `backend/app/retrieval/retriever.py` | Hybrid + diversity (LLD §8.3) | 28 | 3 |
| 30 | `backend/app/investigation/analyst.py` | Build prompt, call adapter, validate | 13, 14 | 3 |
| 31 | `backend/app/investigation/verifier.py` | Steps 1–4 now, value check at CP4 | — | 3, 4 |
| 32 | `backend/app/investigation/composer.py` | Minimal now, full at CP5 | — | 3, 5 |
| 33 | `backend/app/investigation/orchestrator.py` | Pipeline; cache + degraded path at CP5 | 29–32 | 3, 5 |
| 34 | `backend/app/api/questions.py` | Ask, list runs | 33 | 3 |
| 35 | `components/QuestionBar.tsx`, `RunCard.tsx`, `EvidencePane.tsx` | Plain answer + citation list | 26 | 3 |
| 36 | `backend/app/investigation/normalize.py` + `tests/test_normalize.py` | LLD §12 | — | 4 |
| 37 | `tests/test_verifier.py` | LLD §20.1 | 31, 36 | 4 |
| 38 | `backend/app/investigation/conflicts.py` + `tests/test_conflicts.py` | LLD §13 | 36 | 4 |
| 39 | `backend/app/investigation/uncertainty.py` + `tests/test_uncertainty.py` | LLD §14 | 38 | 5 |
| 40 | `tests/test_llm.py` | 429, timeout, invalid JSON, repair, mock miss | 13 | 5 |
| 41 | `components/StateBadge.tsx` | LLD §18.4 table | — | 5 |
| 42 | `backend/app/ingestion/ocr.py` (+ `extract.py` image and scanned-page paths) | LLD §7.3 | 18 | 6 |
| 43 | `make_demo_docs.py` Set B, `api/demo.py` seed, `scripts/acceptance.py`, demo buttons in `HomePage.tsx` | LLD §19, §20.2 | all P0 | 7 |
| 44 | `backend/app/api/evidence.py` | Chunk context, page image | 6 | 8 |
| 45 | `ContradictionMap.tsx`, `WhyThisAnswer.tsx`, `PageViewer.tsx`, grouped `EvidencePane`, history in `WorkspacePage` | P1 UI | 35, 41 | 8 |
| 46 | `README.md`, SPA mount in `main.py` | Run steps, formats, limits; one-port demo | — | 9 |

## 4. IMPLEMENTATION DEPENDENCY GRAPH

```text
Environment (venv, node, .env, git)
  ↓
config → logging → db ───────────────┐
  ↓                                   │
LLM adapter (base, json_utils, recorder, openrouter) + prompts → llm_smoke   [CP1]
  ↓                                   │
validate → extract → clean → chunk → embedder → pipeline → upload API → DocumentsPane   [CP2]
  ↓
index → retriever → analyst → verifier(quote) → composer(min) → orchestrator → questions API → RunCard   [CP3]
  ↓
normalize → verifier(value) → conflicts   [CP4]
  ↓
uncertainty → composer(full) → evidence-only path → run cache → StateBadge   [CP5]
  ↓
ocr   [CP6]  →  Set B + seed + acceptance   [CP7]
  ↓
P1 UI + evidence API   [CP8]  →  README, build, pre-run   [CP9]  →  freeze, rehearse, submit   [CP10]
```

- **Strictly sequential:** everything on the main line. Retrieval needs chunks; the analyst needs retrieval; conflicts need normalised values; uncertainty needs conflicts.
- **Independent of the main line** (can be done whenever there is a wait): `normalize.py`, `conflicts.py`, `uncertainty.py` and their tests are pure functions with no I/O; `make_demo_docs.py`; frontend scaffold; README.
- **Use waits:** `pip install`, `npm install` and the embedding/OCR model downloads run in the background during Checkpoint 1 while the adapter is written.
- Solo rule: one main-line task open at a time. No real parallel work.
- **Emergency order protecting 13:30.** Embeddings and hybrid fusion are supporting infrastructure, not the innovation. If fastembed or fusion threatens the slice, build this first:

  ```text
  PDF → extraction → chunks → BM25 retrieval → LLM analysis → quote verification → answer composition → citation
  ```

  Chunks are stored with `embedding = NULL` and the retriever runs BM25 with per-document diversity (the LLD already defines this BM25-only behaviour, so it is not a design change). Dense embeddings and fusion are added only after the slice works.

## 5. CHECKPOINT-BY-CHECKPOINT EXECUTION PLAN

All commands run from `D:\Algothon` in PowerShell with the venv active (§18).

### Checkpoint 1 — 10:00–10:40 — Boot
- **Objective:** project runs, the LLM answers in valid JSON, a model is pinned.
- **Tasks:** `git init`; create venv; install backend deps; scaffold frontend with Tailwind and `/api` proxy; write files 1–16; warm fastembed and rapidocr once so models download now; check OpenRouter quota on the dashboard; run the smoke test on `openrouter/free` and 2–3 specific free models; pin the best in `.env`; set `LLM_SUPPORTS_JSON_MODE` from the result.
- **Files:** table rows 1–16.
- **Commands:** §18 steps 1–4; `python scripts/llm_smoke.py`; `Invoke-RestMethod http://localhost:8000/api/health`.
- **Expected:** health returns `ok: true` with model name; Vite page loads; smoke test prints, per model: valid JSON yes/no, quotes exact yes/no, latency.
- **Test:** smoke sample is two short passages saying "30 days" and "45 days"; pass = two claims whose quotes are exact substrings.
- **Done:** health OK · SPA blank page loads · one model pinned · first commit.
- **If it fails:** no model gives valid JSON → keep `openrouter/free`, rely on the repair retry, continue. Wheel install fails on this Python → install Python 3.11 and recreate the venv. No API key working → set `LLM_MODE=mock` and continue to Checkpoint 2; resolve the key before 12:00.
- **Not yet:** any ingestion, any UI beyond the scaffold, any styling.

### Checkpoint 2 — 10:40–12:00 — Upload → extract → index
- **Objective:** files become located, embedded chunks.
- **Tasks:** rows 17–27. Generate Set A. Upload through the UI. Inspect chunks in SQLite.
- **Commands:** `python scripts/make_demo_docs.py --set A`; start backend and frontend; `python -c "import sqlite3; c=sqlite3.connect('data/app.db'); print(c.execute('select filename,status,chunk_count from documents').fetchall())"`.
- **Expected:** four Set A documents (invoice as PDF) reach `ready`; chunks carry correct `page` and `section`; `embedding` not NULL.
- **Test:** the agreement's §4.2 chunk has `page = 2`, section containing "4.2"; uploading a `.exe` renamed `.pdf` is rejected; the same file twice shows `duplicate`.
- **Done:** all of the above visible in the documents pane with status chips. Commit.
- **If it fails:** heading detection flaky → store `section = NULL` and move on. DOCX trouble → defer DOCX, convert the policy to PDF for now.
- **Embedding time box:** if `embedder.py` is not producing vectors within 15 minutes of starting it, or by 11:30 at the latest, stop, store NULL embeddings and switch to the emergency order (§4). Do not debug fastembed before the vertical slice exists.
- **Not yet:** OCR, retrieval, questions, upload progress bars, delete-document.

### Checkpoint 3 — 12:00–13:30 — Question → answer → citation
- **Objective:** the first full vertical slice (§6).
- **Tasks:** rows 28–35, built in this order so an answer appears as early as possible: index with BM25 → retriever (BM25 + per-document diversity) → analyst → verifier steps 1–4 → minimal composer → orchestrator → question API → run card. Only once a cited answer is on screen: add dense search and rank fusion to the retriever. Provisional state. Recorder on from the first call.
- **Retrieval rule:** no tuning of retrieval before the slice works. If dense/hybrid is not in by 13:30, it moves to the first task of Checkpoint 4's slack or after Checkpoint 5; the slice ships on BM25.
- **Commands:** ask A1 and A4 in the UI; then set `LLM_MODE=replay` in `.env` and restart.
- **Expected:** an answer with numbered citations; each shows document, page, section, and a quote that is real text from that page.
- **Test:** open the PDF and find each displayed quote by eye; ask A5 → INSUFFICIENT with no answer sentences; repeat A1 in replay → instant, log shows `recording=true`.
- **Done:** A1, A4, A5 behave as above on screen at or before 13:30. Commit.
- **If it fails:** quotes being dropped (model paraphrases) → check the dropped-claim log, switch model via `.env`, lower nothing in the verifier. Draft sentences unusable → composer uses the generated "{document} states: …" sentences only.
- **Not yet:** conflict logic, state rules, cache, styling, contradiction map.

### Break — 13:30–14:00
Eat. If Checkpoint 3 is not done, this buffer is consumed by it and nothing else.

### Checkpoint 4 — 14:00–15:15 — Conflict detection
- **Objective:** competing positions are found by code.
- **Tasks:** rows 36–38; add the value check (verifier step 5) and de-duplication (step 6); put `aspects[].positions[]`, `status`, `basis`, `notes` into the result; show positions as plain text lists in `RunCard`.
- **Commands:** `python -m pytest backend/tests -q`; ask A3 and A6.
- **Expected:** A3 → two positions, "30 days" (Agreement, Amendment) and "45 days" (Invoice). A6 → "60 days" vs "90 days" with a supersession note quoting the Amendment.
- **Test:** unit tests in LLD §20.1 for normalize, verifier, conflicts all pass; A1 shows one position (no false conflict).
- **Done:** tests green; A3 and A6 correct in replay and once live. Commit.
- **If it fails:** a normaliser type is troublesome → ship duration, number, money, percent, boolean; send date and anything unparsed down the `text` path. Model splits one fact into two aspects → that is prompt rule 2; adjust wording, bump `PROMPT_VERSION`, re-record.
- **Not yet:** contradiction map graphics, uncertainty rules, Set B.

### Checkpoint 5 — 15:15–16:00 — Uncertainty and fallbacks
- **Objective:** every result carries a rule-based state and reasons; the app survives a dead LLM.
- **Tasks:** rows 39–41; full composer (LLD §15); evidence-only path; run cache with `fresh` bypass; warnings; `signals`.
- **Commands:** `python -m pytest backend/tests -q`; set `LLM_MODE=mock`, restart, ask an unrecorded question.
- **Expected:** A1 HIGH, A4 MEDIUM, A3 CONFLICT, A5 INSUFFICIENT; the unrecorded question in mock mode returns HTTP 200, `degraded: true`, top passages, state LOW.
- **Test:** unit fixtures for rules 1–9; `test_llm.py` (429 then success, timeout → fallback model, all models fail with a recording present → recording used, all fail with none → `LLMUnavailable`, invalid JSON → repair, double failure → `LLMBadOutput`, mock miss → `LLMUnavailable`); repeat question → `cached: true`.
- **Done:** all four states seen on screen with a badge; fallback demonstrated; tests green. Commit.
- **If it fails:** cache is the first thing to defer (replay mode already makes repeats free). Reason templates can ship as the first line only.
- **Not yet:** Why-panel UI, OCR, Set B.

### Checkpoint 6 — 16:00–16:40 — OCR
- **Objective:** images and scanned pages are indexed with a quality signal.
- **Tasks:** row 42; image extension path; PDF page with < 20 chars → render at 200 DPI → OCR; `ocr_confidence` per chunk; "scan" tag in the documents pane; OCR warning and reason.
- **Commands:** upload `Invoice_INV-2041.png` into a fresh investigation with the other three Set A files; ask A3.
- **Expected:** invoice `ready`, `extraction_method = ocr`; A3 still CONFLICT with the 45-day claim sourced from the PNG and tagged as scanned.
- **Test:** the quote for "45 days" matches (fuzzy threshold 88) and the displayed quote is the OCR chunk's own text; a blank image → `failed`, "No readable text found".
- **Done:** above passes. Commit.
- **If it fails (hard stop 16:40):** keep the invoice as text PDF in Set A, leave image upload enabled only if it works, and state OCR as limited in the README. Do not debug OCR past 16:40.
- **Not yet:** LLM vision fallback, image page viewer.

### Checkpoint 7 — 16:40–17:20 — Second unrelated document set
- **Objective:** validate that the same code and the same prompt work on an unrelated domain. This is a validation activity, not a development one. Closing it opens P1.
- **Order:** (1) `/demo/seed` and `acceptance.py`; (2) Set A acceptance green — this is the core gate; (3) generate Set B and run it through the unchanged system; (4) record the outcome.
- **Tasks:** row 43; Set B documents per LLD §19; home-page buttons; `acceptance.py` covering A1–A7 and B1–B5.
- **Commands:** `python scripts/make_demo_docs.py --set B`; `python scripts/acceptance.py`.
- **Expected:** Set A: tests A–G green. Set B: B1 CONFLICT (18 vs 24), B2 HIGH, B3 CONFLICT (yes vs no), B4 MEDIUM, B5 INSUFFICIENT, with the same code and `PROMPT_VERSION` as Set A.
- **Done:** Set A green; Set B run and every result is either as expected or written down as a known limitation in the README. Grounding (test F) must hold on Set B without exception. Commit.
- **If a Set B case fails:**
  - It is a defect where the code does not do what the LLD says (crash, wrong parse of a form the LLD lists) → fix the defect, re-run Set A, then Set B.
  - It is outside the explicitly supported conflict/normalisation scope → **do not** change the prompt, conflict rules, uncertainty rules or architecture. Document the limitation, pick the Set B questions that work for the demo (B1 is the primary), move on.
  - Never special-case a document, party name or question.
- **Not yet:** any P1 component.

### Checkpoint 8 — 17:20–19:30 — Evidence UI, Why, Contradiction, History
- **Objective:** the innovation is visible at a glance.
- **Tasks, in this order (each is shippable alone):**
  1. `ContradictionMap` (aspect → positions → document chips).
  2. `WhyThisAnswer` (reasons + signal row).
  3. Evidence pane grouped by position; citation click selects and scrolls to the card.
  4. Styling pass: grid, badges, typography, empty and error states.
  5. History: older runs collapsed, click to expand.
  6. `api/evidence.py` + `PageViewer` (page image with boxed quote).
- **Commands:** frontend dev server; walk the demo script.
- **Expected:** §10 screen descriptions match.
- **Test:** manual UI tests in §11D.
- **Done:** demo path A1 → A7 → A3 → Why → A5 → Set B looks finished. Commit after each numbered task.
- **If it fails:** cut from the bottom: page viewer first, then history, then grouping. Items 1, 2 and 4 are the must-haves.
- **Not yet:** timeline, graph, animation, hosted deploy.

### Checkpoint 9 — 19:30–20:15 — Deployment, README, pre-run
- **Objective:** one-command local demo from a clean state.
- **Tasks:** row 46; `npm run build`; serve `frontend/dist` from FastAPI; README (what it is, run steps, supported formats actually tested, stated limits from LLD §13, architecture principle); delete `data/app.db`, seed A and B, run every demo question once in `replay` so recordings and cache exist; push to GitHub.
- **Commands:** §18 steps 6–9.
- **Expected:** `http://localhost:8000` serves the whole app; all demo questions answer instantly.
- **Test:** disconnect the network and run the demo script end to end.
- **Done:** offline run-through succeeds; repo pushed. Commit.
- **If it fails:** static mount trouble → demo with the Vite dev server and backend side by side. No tunnel or hosted deploy unless the submission form demands a live URL.
- **Not yet:** P2, unless this checkpoint finished early and everything is green.

### Checkpoint 10 — 20:15–22:00 — Freeze, rehearsal, backup, submission
- **20:15 feature freeze.** Bug fixes only; each fix followed by `pytest` and `acceptance.py`.
- **20:15–21:00:** three timed rehearsals of §13; fix only what breaks the script.
- **21:00–21:20:** record the backup video of a full run.
- **21:20–21:40:** backup zip (§18 step 10); final commit and push; verify the repo link in a private window.
- **21:40–22:00:** submit; confirm links open; Discord requirement satisfied.
- **Done:** §17 checklist fully ticked.
- **If it fails:** submit what is green at 21:40. The hour to 23:00 is for submission problems only, not features.

## 6. FIRST WORKING VERTICAL SLICE (due 13:30)

```text
upload → validate → extract (PDF/TXT/DOCX) → clean → chunk → embed → SQLite
ask → retrieve (hybrid + diversity) → ONE LLM call → verify quotes → provisional state → compose → show citations
```

Files that must exist, and nothing more:

- Backend: `config.py`, `db.py`, `schemas.py`, `logging_utils.py`, `main.py`
- `llm/`: `base.py`, `json_utils.py`, `recorder.py`, `openrouter.py`
- `ingestion/`: `validate.py`, `extract.py`, `clean.py`, `chunk.py`, `pipeline.py`
- `retrieval/`: `embedder.py`, `index.py`, `retriever.py`
- `investigation/`: `prompts.py`, `analyst.py`, `verifier.py` (steps 1–4), `composer.py` (minimal), `orchestrator.py`
- `api/`: `investigations.py`, `documents.py`, `questions.py`, `demo.py` (health)
- Frontend: `api/client.ts`, `api/types.ts`, `api/hooks.ts`, `App.tsx`, `HomePage.tsx`, `WorkspacePage.tsx`, `DocumentsPane.tsx`, `QuestionBar.tsx`, `RunCard.tsx`, `EvidencePane.tsx`

Deliberately absent at this point: OCR, `normalize.py`, `conflicts.py`, `uncertainty.py`, cache, seed endpoint, styling. The result JSON already has its final shape (LLD §5) with `aspects[].positions` empty and `reasons` holding one line, so the frontend never has to be reworked.

**Emergency order.** If embeddings, fastembed or hybrid fusion put 13:30 at risk, drop `embedder.py` and the dense half of `index.py` / `retriever.py` from the list above and build:

```text
PDF → extraction → chunks → BM25 retrieval → LLM analysis → quote verification → answer composition → citation
```

TXT and DOCX extraction, dense embeddings and rank fusion are then added after the slice works, in that order. What judges score is trustworthy evidence, verified citations, conflict detection and uncertainty handling; retrieval quality on a ten-page corpus is not the differentiator and must not delay the slice.

This milestone outranks everything else in the plan. If it is not reached by 13:30, the break buffer is spent on it and no other work starts.

## 7. LLM IMPLEMENTATION PLAN

| Stage | LLM used |
|---|---|
| Ingestion, OCR, cleaning, chunking | No |
| Embeddings | No (local ONNX model) |
| Retrieval | No |
| **Evidence analysis** | **Yes — one call per uncached question** |
| Quote and value verification | No |
| Conflict detection | No |
| Uncertainty state and reasons | No |
| Answer composition, citations | No |
| Cache, UI | No |

**Request/response flow**
1. `orchestrator` computes the cache key; a hit returns the stored run with no LLM involvement.
2. `retriever` returns E1..E10.
3. `analyst` builds `system` (prompt v1) and `user` (question + `<evidence>` blocks) and calls `LLMClient.complete_json(system, user, validate)`.
4. `recorder` checks the mode: `replay`/`mock` with a recording → return it; `mock` without → `LLMUnavailable`; otherwise go to the network.
5. `openrouter` posts to `/chat/completions` (temperature 0, max tokens 2000, JSON mode only if flagged), serialised with a 3 s minimum gap and 45 s timeout.
6. **Failure chain, exactly:**
   1. Primary configured model.
   2. Retry the primary once (after `Retry-After`, capped at 10 s).
   3. Each configured fallback model once, in order.
   4. A recorded run for this exact prompt, if one exists.
   5. Deterministic evidence-only mode.

   One API key only. No key rotation, no multiple-key handling.
7. Parse: strip fences → outermost `{…}` → `json.loads` → validate. On failure, one repair request quoting the error. Second failure → `LLMBadOutput`, which continues down the chain from step 4.
8. Success is written to `data/llm_recordings/<sha256>.json`.
9. Evidence-only result: top 5 passages, state LOW, `degraded: true`, warning shown, stored in history, never served from cache.

**Configuration:** `OPENROUTER_MODEL` (pinned at Checkpoint 1), `OPENROUTER_FALLBACK_MODELS`, `LLM_MODE`, `LLM_TIMEOUT_S`, `LLM_MIN_GAP_S`, `LLM_MAX_TOKENS`, `LLM_SUPPORTS_JSON_MODE`, `PROMPT_VERSION`.

**Mode by activity**

| Activity | Mode |
|---|---|
| Checkpoint 1 smoke test, first run of each new question | `live` |
| All development after Checkpoint 3, unit tests, UI work | `replay` |
| Fallback testing | `mock` |
| Demo | `replay` (rehearsed questions offline; a new question goes live) |

Any prompt edit bumps `PROMPT_VERSION` and invalidates recordings and cache, so prompt changes are batched and rare. No other LLM call exists or will be added.

## 8. DATABASE IMPLEMENTATION ORDER

Schema is LLD §4, created in one bootstrap at startup (`CREATE TABLE IF NOT EXISTS`), in this order: `investigations` → `documents` → `chunks` → `runs`, then indexes.

| Event | Writes |
|---|---|
| Create investigation | `investigations` row |
| Upload (per accepted file) | `documents` row, status `queued` (or `duplicate`, terminal) |
| Background processing | `documents.status` → `extracting` → `indexing`; `chunks` rows with page, section, paragraph_index, text, text_hash, extraction_method, ocr_confidence, embedding; then `documents` → `ready` with page_count, chunk_count, extraction_method — or `failed` with error_message |
| Ask question | Nothing until the run finishes |
| Run finished | `runs` row: question, cache_key, state, degraded, result_json, model, latency_ms |

- **Relationships:** documents → investigation; chunks → document (+ denormalised investigation_id for fast filtering); runs → investigation. Claims, positions, reasons live inside `result_json`.
- **Cache lookup:** `SELECT result_json FROM runs WHERE cache_key = ? AND degraded = 0 ORDER BY created_at DESC LIMIT 1`. Key = SHA-256 of `PROMPT_VERSION | OPENROUTER_MODEL | sorted sha256 of ready documents | lower-cased question`. A hit returns the stored result with `cached: true` and inserts nothing. Uploading another document changes the key automatically.
- **Citations:** the result's document, page, section, paragraph are read from `chunks` by `chunk_id` at compose time.

## 9. API IMPLEMENTATION ORDER

Contract is LLD §6; nothing added.

| # | CP | Method + path | Request → response | Service | Errors | Test |
|---|---|---|---|---|---|---|
| 1 | 1 | `GET /api/health` | — → `{ok, llm_mode, model, embedder, ocr}` | config, lazy checks | — | `Invoke-RestMethod` returns ok |
| 2 | 2 | `POST /api/investigations` | `{title?}` → `{id, title, created_at}` | db | — | create from Home, URL becomes `/i/<id>` |
| 3 | 2 | `GET /api/investigations/{id}` | — → investigation + documents + run summaries | db | 404 `investigation_not_found` | reload workspace |
| 4 | 2 | `POST /api/investigations/{id}/documents` | multipart `files` → `{accepted, rejected}` | `validate`, `pipeline.process_document` (background) | 400 `no_files`, `too_many_files`; 404 | upload 4 good + 1 bad file |
| 5 | 2 | `GET /api/investigations/{id}/documents` | — → `Document[]` | db | 404 | statuses change while polling |
| 6 | 3 | `POST /api/investigations/{id}/questions` | `{question, fresh?}` (+`?debug=1`) → result | `orchestrator.run_investigation` | 400 `empty_question`, `question_too_long`; 404 | A1 returns claims |
| 7 | 3 | `GET /api/investigations/{id}/runs` | — → result `[]` | db | 404 | reload keeps answers |
| 8 | 7 | `POST /api/demo/seed` | `{set}` → investigation | copies `demo_docs/set_x`, same path as upload | 400 bad set | button opens a ready workspace |
| 9 | 8 | `GET /api/chunks/{id}` | — → `{chunk, prev, next}` | db | 404 | evidence card "show context" |
| 10 | 8 | `GET /api/documents/{id}/pages/{page}/image?q=` | — → PNG | PyMuPDF render + `search_for` | 404 `document_not_found`, `page_out_of_range` | page shows boxed quote |

## 10. FRONTEND IMPLEMENTATION ORDER

```text
┌────────────────┬──────────────────────┬────────────────────┐
│ DOCUMENTS      │ INVESTIGATION        │ EVIDENCE           │
│ upload zone    │ run cards            │ evidence cards     │
│ file + status  │ state · answer · [n] │ doc · page · quote │
├────────────────┴──────────────────────┴────────────────────┤
│ Ask a question about these documents…                      │
└────────────────────────────────────────────────────────────┘
```

**P0**

| # | CP | Piece | Visible on screen |
|---|---|---|---|
| 1 | 2 | Home | Title field + "Start investigation"; later two demo buttons |
| 2 | 2 | Workspace | Header with investigation title; three columns |
| 3 | 2 | Upload | Drop zone and file picker; rejected files listed with reason |
| 4 | 2 | Processing status | One row per file: name, chip (Queued / Extracting / Indexing / Ready / Failed / Duplicate), page count, error text; polls every second until all terminal |
| 5 | 3 | Question input | Text box + Ask; disabled with "Upload a document to begin" when nothing is ready; spinner with the fixed stage list while waiting |
| 6 | 3 | Answer | Run card: question, headline, sentences with `[n]` chips |
| 7 | 3 | Evidence | Right column: one card per claim — `[n]`, file name, "p.2 · 4.2 Payment Terms", quote block |
| 8 | 5 | State badge | Icon + words per LLD §18.4, first reason beside it; warnings listed |
| 9 | 5 | Basic inspection | Clicking `[n]` highlights its card; for INSUFFICIENT / degraded, "Related passages" list |

**P1** (Checkpoint 8, in this order)

| # | Piece | Visible on screen |
|---|---|---|
| 10 | Contradiction map | Inside conflict run cards: aspect label, one column per position ("30 days" · "45 days"), document chips with page under each, "≠" between |
| 11 | Why This Answer | Collapsible block: bullet reasons; one line of counts (passages confirmed, documents, dropped) |
| 12 | Grouped evidence | Evidence column split by position headers when in conflict; "Scanned image" tag |
| 13 | Polish | Grid `280px 1fr 380px`, badge colours, spacing, empty states |
| 14 | History | Previous runs collapsed to question + badge; click to expand; conflict count in header |
| 15 | Page viewer | Modal with the rendered page and the quote boxed |

## 11. TESTING IMPLEMENTATION PLAN

**A. Unit (pytest, no network) — `backend/tests/`**

| Area | Input | Expected | Pass |
|---|---|---|---|
| Normalisation | "thirty (30) days", "30 days", "net 30" | same key | equal keys |
| | "2 weeks" vs "14 days" | same key | equal |
| | "$48,500.00" vs "USD 48,500" | same key | equal |
| | "1.5 percent" vs "1.5%" | same key | equal |
| | "15 February 2024" | `date:2024-02-15` | equal |
| | "not permitted" / "permitted" | no / yes | negative cue wins |
| | "03/04/2024" | text key | not parsed as date |
| Quote matching | exact, extra whitespace, ellipsis, OCR typo | verified | pass; displayed quote is a span of the chunk |
| | fabricated quote, unknown `E9`, 5-char quote | dropped | reason recorded |
| Value verification | quote says "45 days", value "30 days" | kept, `explicit=false`, no position key | cannot conflict |
| Conflict | 30 / 30 / 45 from three documents | conflict, positions 2 + 1 | status and counts |
| | scopes "domestic" vs "export" | complementary | no conflict |
| | two values in one chunk | no conflict | status |
| | money vs percent in one aspect | no conflict | status |
| Uncertainty | one fixture per rule 1–9 | the rule's state | exact state + first reason |
| LLM adapter | 429 then 200 | one retry, success | call count 2 |
| | timeout on primary, fallback OK | fallback model used | `model` field |
| | every model fails, recording exists | recording returned | `from_recording` true |
| | every model fails, no recording | `LLMUnavailable` → evidence-only | raised |
| | invalid JSON then valid on repair | success | call count 2 |
| | invalid twice | `LLMBadOutput` | raised |
| | mock mode, no recording | `LLMUnavailable` | raised |

**B. Integration (live server, replay mode)** — covered by `scripts/acceptance.py` setup: seed → poll until ready → ask. Pass = every document `ready`, every question returns HTTP 200 with a valid result shape.

**C. Acceptance A–H (LLD §20.2)**

| Test | Input | Pass condition |
|---|---|---|
| A Normal | A1, B2 | state HIGH or MEDIUM; expected value in a claim |
| B Cross-document | A2, A7 | A2 cites ≥ 3 documents; A7 cites Invoice and Policy |
| C Conflict | A3, A6, B1, B3 | state CONFLICT; exactly the expected positions; nothing marked preferred |
| D Missing | A5, B5 | INSUFFICIENT; `answer` empty |
| E Why | all | non-empty `reasons` and `signals` |
| F Grounding | every claim | quote is a substring of its chunk; document/page equal the chunk row |
| G Isolation | corrupt PDF + valid TXT; mock mode unrecorded question | one failed, one ready; HTTP 200 `degraded: true` |
| H Generalisation (validation) | B1–B5 | run with the same code and `PROMPT_VERSION` as Set A; grounding holds on every claim; each expected state is met or the gap is documented as an out-of-scope limitation. Nothing is changed to make Set B pass |

**D. Manual UI** — every citation chip selects the right card · every displayed quote found in the source file by eye · conflict map chips match the evidence cards · Why panel reasons match the badge · reload keeps history · question bar disabled with no ready document · narrow window still usable.

**E. Failure**

| Case | Input | Expected | Pass |
|---|---|---|---|
| Duplicate | same file twice | second is `duplicate` | not re-indexed |
| Unsupported | `.xlsx` | rejected with reason | others proceed |
| Corrupted | truncated PDF | `failed` + message | others `ready` |
| OCR failure | blank PNG | `failed`, "No readable text found" | app unaffected |
| Embedding failure | bad `EMBED_MODEL` name | chunks stored, BM25-only, health shows `unavailable` | questions still answer |
| LLM timeout / 429 / invalid JSON | unit tests above + mock mode | evidence-only result | HTTP 200, `degraded` |
| No documents | ask immediately | INSUFFICIENT, "No processed documents…" | no error |

## 12. DEMO DATA IMPLEMENTATION

Produced by `scripts/make_demo_docs.py` (PyMuPDF for PDFs and for rendering the invoice page to PNG; python-docx for DOCX). Fictional parties. Files are committed under `demo_docs/`.

**Set A — vendor contract (Orion Logistics / Kestrel Foods)**

| File | Facts |
|---|---|
| `Master_Services_Agreement.pdf` (3 pages) | effective 10 Jan 2024; term 24 months; §4.2 payment within thirty (30) days; §4.3 late fee 1.5% per month; §9.1 termination 60 days' notice |
| `Amendment_1.pdf` | 15 Feb 2024; clause 4.2 unchanged, 30 days; "replaces clause 9.1": 90 days' notice |
| `Invoice_INV-2041.png` (and `.pdf` twin for pre-OCR work) | 1 Mar 2024; USD 48,500; "Payment due within 45 days" |
| `Vendor_Payment_Policy.docx` | late fee 1.5% per month; invoices above USD 25,000 approved by the Finance Director |

| # | Question | State | Expected output | Shows |
|---|---|---|---|---|
| A1 | What is the late payment fee? | HIGH | 1.5% per month; Agreement + Policy | normal answer |
| A7 | What is the invoice total, and who has to approve it? | MEDIUM | USD 48,500 (Invoice); Finance Director (Policy) | cross-document |
| A2 | What payment terms apply after the amendment, and does the invoice follow them? | CONFLICT | 30 days (Agreement, Amendment) vs 45 days (Invoice) | cross-document + conflict |
| A3 | Are the payment terms consistent across the documents? | CONFLICT | same positions | conflict, map, Why |
| A4 | Who approves invoices above USD 25,000? | MEDIUM | Finance Director; one document | single-source reason |
| A5 | What is the warranty period for the equipment? | INSUFFICIENT | no answer | missing evidence |
| A6 | How much notice is needed to terminate the agreement? | CONFLICT | 60 vs 90 days + supersession note | no silent resolution |

**Set B — HR (Brightwave Technologies), unrelated**

| File | Facts |
|---|---|
| `Employee_Handbook.pdf` (2 pages) | annual leave 18 days; remote work permitted up to two days a week; probation six months; notice period 30 days |
| `Offer_Letter.docx` | annual leave 24 days; probation 6 months; joining 1 Aug 2025 |
| `HR_Memo_2025-07.txt` | "Effective 1 July 2025, remote work is not permitted for any employee." |

| # | Question | State |
|---|---|---|
| B1 | How many days of annual leave do employees get? | CONFLICT (18 vs 24) |
| B2 | How long is the probation period? | HIGH |
| B3 | Is remote work permitted? | CONFLICT (yes vs no) |
| B4 | What is the notice period? | MEDIUM |
| B5 | How much is the health insurance cover? | INSUFFICIENT |

Rules:
- Set B exists to show: same code + same prompt + different domain = working investigation system.
- It is written only after Set A's core acceptance tests pass, and it is never used to tune the prompt, conflict rules, uncertainty rules or architecture.
- A7 and B1–B5 are validation and demo questions only. If one falls outside the supported conflict/normalisation scope, the limitation is documented in the README and the demo uses the questions that work.
- Only defects against the LLD are fixed, and each such fix is followed by a full Set A re-run.
- No file name, party name or question string appears anywhere in application code.

## 13. DEMO SCRIPT (about 4 minutes)

| # | Time | Click / ask | System shows | Say | Criterion |
|---|---|---|---|---|---|
| 1 | 0:00 | Home page | Title, two demo buttons | "Answers from documents are only useful if you can check them and know when not to trust them." | Problem Understanding |
| 2 | 0:20 | "Load contract case" | Four files go Queued → Ready; invoice tagged "scan" | "PDF, Word and a scanned invoice, read locally." | Functionality |
| 3 | 0:45 | Ask A1 | Strong evidence badge; "1.5% per month"; two citations; click `[1]` → page, section, quote | "Every citation is checked against the stored text before you see it." | Functionality, Innovation |
| 4 | 1:15 | Ask A7 | Moderate evidence; invoice total from the Invoice, approver from the Policy | "It combines documents and keeps each source separate." | Functionality |
| 5 | 1:40 | Ask A3 | **Conflict detected**; no single answer | "A normal RAG app would have said 30 days." | Innovation |
| 6 | 1:55 | Point at the contradiction map; click the Invoice chip | 30 days ← Agreement, Amendment · 45 days ← Invoice; evidence grouped by side | "Two documents against one, and it does not pick a winner." | Innovation, UI/UX |
| 7 | 2:15 | Open "Why this answer?" | Reasons list and counts | "This state is computed by rules, not by the model's opinion of itself." | Innovation, Problem Understanding |
| 8 | 2:35 | Ask A5 | Insufficient evidence; related passages only | "It refuses to guess." | Problem Understanding |
| 9 | 2:50 | (same screen) | — | "No answer is still an answer you can rely on." | Impact |
| 10 | 3:00 | Home → "Load HR case" | Three unrelated files Ready | "Different domain, same code, nothing tuned." | Functionality |
| 11 | 3:15 | Ask B1 (and B3 if time) | Conflict: 18 vs 24 days | "It generalises: leave days here, payment terms before." | Functionality, Impact |
| 12 | 3:40 | — | — | "The LLM interprets evidence. The application verifies it. Rules decide conflict and confidence. The answer is built only from what survived." | Presentation |

Optional if asked "what if the documents say which one wins?": ask A6 and show the supersession note beside the conflict.

## 14. SCORECARD MAPPING

| Feature | Innov. 20 | Problem 20 | Function 25 | UI/UX 15 | Impact 10 | Present. 10 |
|---|---|---|---|---|---|---|
| Conflict detection + contradiction map | ● | ● | ● | ● | ● | ● |
| Deterministic evidence state + Why panel | ● | ● | ● | ● | | ● |
| Verified, DB-sourced citations | ● | ● | ● | | ● | |
| INSUFFICIENT instead of guessing | | ● | ● | | ● | ● |
| Cross-document answers | | ● | ● | | | |
| Multi-format upload + OCR + status | | ● | ● | ● | | |
| Second document set | | | ● | | ● | ● |
| Three-pane workspace | | | | ● | | ● |
| Replay / evidence-only resilience | | | ● | | | ● |

Highest value, in order: (1) conflict detection with the map, (2) verified citations, (3) rule-based state with Why, (4) INSUFFICIENT, (5) Set B. These five are what the demo script spends its time on.

## 15. FAILURE / RECOVERY PLAN

| Failure | Primary path | Fallback | Demo-safe state |
|---|---|---|---|
| OpenRouter down | Primary model | Retry once → fallback model(s) → recorded run → evidence-only | `LLM_MODE=replay`: rehearsed questions from recordings/cache |
| Rate-limited (429) | Wait `Retry-After`, retry primary once | Fallback model(s) → recorded run → evidence-only | Replay |
| Free model withdrawn | Pinned model | Change `OPENROUTER_MODEL`; `openrouter/free` | Replay (recordings are model-independent once made) |
| Invalid JSON | Tolerant parse | One repair request | Evidence-only for that question |
| Bad quotes (paraphrase) | Verifier drops claims | Switch model; tighten prompt rule 3, bump version, re-record | Fewer claims shown, none wrong |
| Embeddings fail | fastembed | BM25-only retrieval, health warns | Works on keyword search |
| OCR fails | rapidocr | Invoice as text PDF | Set A with PDF invoice; OCR listed as limited |
| One corrupt document | Per-document status | — | That file `failed`, others usable |
| Frontend breaks | Fix last change | `git checkout` last checkpoint commit for `frontend/` | Last committed UI |
| Static mount / deploy fails | One-port FastAPI | Vite dev server + backend | Two local processes |
| Internet unreliable | Local server | Replay mode | Whole demo offline; backup video |
| Out of time | Cut rules §16 | — | Last green checkpoint commit |

After Checkpoint 9 the demo does not need the LLM API: both sets are seeded, every scripted question is recorded and cached, and the server is local.

## 16. TIME-CUT STRATEGY

| If behind at | Remove |
|---|---|
| **12:00** (ingest not done) | Embeddings (NULL, BM25-only — emergency order §4); heading/section detection (store NULL); DOCX and TXT until after the slice (PDF only); duplicate handling; header/footer removal |
| **13:30** (no vertical slice) | Use the break. Dense search and fusion (stay BM25); draft-sentence filtering (compose from claims only); `?debug`; any styling. Nothing else starts until the slice works |
| **15:15** (conflict not done) | Date and text normalisers (fall to `text` path); supersession notes; A6 from the demo |
| **16:40** (uncertainty/OCR not done) | OCR entirely (invoice stays text PDF, README says so); run cache (replay covers it); secondary reason templates |
| **17:20** (Checkpoint 7 not closed) | If Set A acceptance is not green: no P1 until it is. If only Set B cases are off: document them as limitations, choose the working Set B questions for the demo, and move on — no prompt or rule changes. P2 is cancelled for the day |
| **19:30** (P1 UI unfinished) | Page viewer, then history, then grouped evidence. Keep map + Why + styling. No hosted deploy, no tunnel |
| **20:15** (freeze) | Everything not committed and green. Remaining time: acceptance run, README, pre-run, rehearsal, video, submit |

P2 is attempted only if Checkpoint 9 is complete before 20:15.

## 17. DEFINITION OF DONE

```text
[ ] application starts with one command
[ ] investigation can be created
[ ] multiple documents upload
[ ] documents process, with visible status
[ ] question works
[ ] evidence is retrieved (every relevant document represented)
[ ] LLM analyst works
[ ] quotes are verified
[ ] citations are DB-sourced
[ ] normal answer works (A1)
[ ] cross-document answer works (A7, A2)
[ ] conflict works (A3, B1)
[ ] uncertainty works (HIGH, MEDIUM, LOW seen)
[ ] insufficient evidence works (A5, B5)
[ ] evidence-only fallback works (mock mode)
[ ] LLM failure is handled (test_llm.py green)
[ ] Set A works
[ ] Set B works on the unchanged system (any out-of-scope gap documented in the README)
[ ] unit tests and acceptance A–H pass
[ ] UI is usable at laptop resolution
[ ] demo questions are rehearsed three times
[ ] replay/cache demo runs with the network off
[ ] README is complete (run steps, tested formats, stated limits)
[ ] source code is committed and pushed
[ ] backup zip and backup video exist
[ ] submission links open in a private window
[ ] Discord requirement is satisfied throughout the hackathon
```

## 18. FINAL IMPLEMENTATION COMMAND SEQUENCE (PowerShell, from `D:\Algothon`)

```powershell
# 1. environment
git init
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# 2. dependencies
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
npm create vite@latest frontend -- --template react-ts
npm --prefix frontend install
npm --prefix frontend install react-router-dom @tanstack/react-query lucide-react tailwindcss @tailwindcss/vite
Copy-Item backend\.env.example backend\.env      # then add OPENROUTER_API_KEY

# 3. backend (terminal 1)
uvicorn app.main:app --app-dir backend --reload --port 8000

# 4. frontend (terminal 2)
npm --prefix frontend run dev                    # http://localhost:5173, /api proxied to :8000

# 5. tests
python scripts\llm_smoke.py
python -m pytest backend\tests -q
python scripts\acceptance.py

# 6. demo data
python scripts\make_demo_docs.py --set A
python scripts\make_demo_docs.py --set B
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/demo/seed -ContentType application/json -Body '{"set":"A"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/demo/seed -ContentType application/json -Body '{"set":"B"}'

# 7. replay / demo mode (set LLM_MODE=replay in backend\.env, or per session:)
$env:LLM_MODE = "replay"

# 8. build frontend
npm --prefix frontend run build

# 9. local demo, one port
uvicorn app.main:app --app-dir backend --port 8000     # open http://localhost:8000

# 10. backup
git add -A; git commit -m "Checkpoint N"
git archive -o ..\algothon-source.zip HEAD
Compress-Archive -Path data -DestinationPath ..\algothon-data.zip -Force

# 11. submission
git remote add origin <repo-url>
git push -u origin main
```

`git add -A; git commit` is run at the end of every checkpoint. The data zip matters: recordings and the database are git-ignored and are what make the offline demo work.

## 19. CLAUDE CODE EXECUTION MODE

**Immutable during Phase 6:** the frozen HLD, the frozen LLD, and this plan's execution architecture.

Operating protocol for every implementation session:

1. One checkpoint, or one numbered task inside it, per instruction.
2. Read the named LLD sections first; implement exactly those.
3. Small changes; run the relevant test after each; never skip a failing test.
4. When a problem appears: solve it inside the existing design first, with the smallest implementation change.
5. No new frameworks, services, databases, queues, architectural patterns or dependencies. No new files beyond §3. No new abstraction.
6. No silent change to requirements, architecture, schema, API contract, prompt rules, conflict rules or uncertainty rules.
7. A genuine architectural blocker means **stop and report** — the blocker, why it matters, the smallest possible correction — and wait. No autonomous redesign.
8. No P1 before Checkpoint 7 is closed; no P2 before Checkpoint 9.
9. No document names, party names or question strings in application code. Nothing is changed to make Set B pass.
10. Protect 13:30: before the vertical slice works, nothing is perfected; use the emergency order if retrieval or embeddings stall.
11. Development runs in `LLM_MODE=replay`; say so before making any live call beyond the first run of a new question.
12. End every task with a report: files changed · commands run · test results · failures · remaining work for this checkpoint. Then stop.

Standard instruction:

```text
Implement only Checkpoint <N> / Task <M> from docs/PHASE5_PLAN.md, following docs/LLD.md sections <§…>.
The HLD, LLD and Phase 5 plan are frozen. Do not change architecture, schema, API contract,
dependencies, prompt rules, conflict rules or uncertainty rules. Solve problems within the existing
design using the smallest change. If you hit a genuine architectural blocker, stop and report the
blocker, why it matters and the smallest correction; do not redesign.
Use LLM_MODE=replay unless a live call is required for this task.
When done, run <tests for this checkpoint> and report: files changed, commands executed, test results,
failures, and what remains for this checkpoint. Then stop.
```

## 20. PHASE 5 FINAL OUTPUT

### A. Master implementation checklist

```text
CP1  [ ] git + venv + deps   [ ] frontend scaffold   [ ] config/db/health   [ ] LLM adapter + recorder
     [ ] smoke test          [ ] model pinned        [ ] quota checked      [ ] models downloaded
CP2  [ ] validate  [ ] extract PDF/TXT/DOCX  [ ] clean  [ ] chunk  [ ] embed  [ ] pipeline
     [ ] investigation + document APIs  [ ] Set A generated  [ ] documents pane with status
CP3  [ ] index  [ ] retriever + diversity  [ ] analyst  [ ] quote verifier  [ ] composer (min)
     [ ] orchestrator  [ ] question API  [ ] run card + evidence list  [ ] switch to replay
CP4  [ ] normalize + tests  [ ] value check  [ ] conflicts + tests  [ ] positions in result
CP5  [ ] uncertainty + tests  [ ] full composer  [ ] evidence-only  [ ] cache  [ ] test_llm  [ ] badge
CP6  [ ] OCR for images and scanned pages  [ ] OCR signals  [ ] PNG invoice in Set A
CP7  [ ] seed endpoint + buttons  [ ] Set A acceptance green  [ ] Set B validated on unchanged code
     [ ] any out-of-scope Set B gap documented
CP8  [ ] contradiction map  [ ] Why panel  [ ] grouped evidence  [ ] polish  [ ] history  [ ] page viewer
CP9  [ ] build + static mount  [ ] README  [ ] pre-run demo questions  [ ] offline run  [ ] push
CP10 [ ] freeze  [ ] 3 rehearsals  [ ] video  [ ] backup zips  [ ] submit  [ ] links verified
```

### B. 12-hour timeline

| Time | Work |
|---|---|
| 10:00–10:40 | CP1 Boot |
| 10:40–12:00 | CP2 Upload → index |
| 12:00–13:30 | CP3 First end-to-end answer |
| 13:30–14:00 | Break / buffer |
| 14:00–15:15 | CP4 Conflict |
| 15:15–16:00 | CP5 Uncertainty + fallbacks |
| 16:00–16:40 | CP6 OCR |
| 16:40–17:20 | CP7 Set B + acceptance (P0 complete) |
| 17:20–19:30 | CP8 P1 UI |
| 19:30–20:15 | CP9 Build, README, pre-run |
| 20:15–22:00 | CP10 Freeze, rehearse, back up, submit |
| 22:00–23:00 | Slack for submission problems only |

### C. Critical path

LLM adapter → ingestion (PDF) → BM25 retriever with document diversity → analyst → quote verifier → orchestrator → run card **(13:30)** → normalise → conflicts → uncertainty → Set A acceptance → Set B validation → contradiction map + Why panel → pre-run in replay.

Dense embeddings and hybrid fusion, OCR, DOCX, cache, page viewer, history and deployment are off the critical path. They are added after the slice and are the first things cut.

### D. Top 10 risks

1. Free model paraphrases quotes, so claims are dropped and answers are thin.
2. Free-tier daily quota runs out before rehearsal.
3. Vertical slice slips past 13:30.
4. Model groups one fact under two aspects, hiding a conflict.
5. Malformed JSON from the pinned model.
6. OCR text too noisy for the 45-day quote to match.
7. A Set B case (most likely the yes/no conflict, B3) falls outside the supported scope; handled by documenting it, not by changing the system.
8. Wheel or model-download problems on Windows at Checkpoint 1.
9. P1 polish eats the deploy and rehearsal time.
10. Recordings invalidated by a late prompt change, forcing live re-runs with little quota left.

### E. Top 10 "DO NOT DO THIS" rules

1. Do not add a second LLM call.
2. Do not let any model-supplied document, page, section or quote reach the screen.
3. Do not loosen the verifier to make an answer appear.
4. Do not pick or hint at a winning side in a conflict.
5. Do not special-case Set A or Set B in code, and do not change the prompt or rules to make Set B pass.
6. Do not start P1 before Checkpoint 7 is closed.
7. Do not perfect retrieval or embeddings before the 13:30 slice works; use the BM25 emergency order.
8. Do not redesign during implementation, and do not add dependencies, frameworks, Docker, hosting or a second API key.
9. Do not debug one item past its checkpoint; apply the cut rule.
10. Do not change code after 20:15 without re-running pytest and the acceptance script.

### F. Exact first task at 10:00

Open PowerShell in `D:\Algothon`, run `git init` and `py -3.11 -m venv .venv`, start `pip install -r backend\requirements.txt` (after creating that file from LLD §2), and while it installs, open the OpenRouter dashboard to confirm the key works and note the free-tier request limits. Then give Claude Code: "Implement only Checkpoint 1 from docs/PHASE5_PLAN.md…".

**PHASE 5 COMPLETE — READY FOR IMPLEMENTATION.**

