# APPENDIX — ALG-AI-02 Intelligent Document Investigator — Final HLD (Frozen)

Kept here unchanged as the source of truth. Copy into `docs/HLD.md` at Checkpoint 1.

Revision 2. Changes from revision 1: solo developer, OpenRouter free models behind an adapter, local OCR, one LLM call per question, run cache and replay mode, mandatory second document set, cross-document reasoning promoted to P0, sequential 10-checkpoint schedule.

---

## 1. Executive Summary

A single-process web app (React SPA → FastAPI → SQLite) that answers questions over uploaded documents and treats retrieved text as **evidence** rather than context. One LLM call per question extracts claims with verbatim quotes. Application code then verifies every quote against stored text, compares claims across documents, decides the evidence state by rule, and assembles the answer only from what survived verification.

Central principle:

> LLMs interpret evidence. The application verifies evidence. Deterministic logic evaluates conflicts and uncertainty. The final answer is generated only from verified evidence.

Built by one developer in 12 hours on a free OpenRouter model, so the design budgets LLM calls tightly, caches every run, and has a non-LLM fallback at every stage.

## 2. Problem Definition

ALG-AI-02: information is scattered across PDFs, images and text documents; users need answers without reading everything. Required: multiple formats, extraction/indexing, natural-language Q&A, source/section references, conflict detection, uncertainty handling.

## 3. Product Vision

Not "chat with PDFs". An investigator that proves its answers, surfaces conflicting evidence, and says when it should not be trusted. Workflow: ASK → RETRIEVE → ANSWER → PROVE → COMPARE → WARN.

## 4. Goals

1. A reliable end-to-end path: upload → ask → cited answer.
2. Visible, explainable conflict detection on comparable claims.
3. A deterministic evidence state with plain-language reasons.
4. Citations that are verified server-side, never model-asserted.
5. Works on two unrelated document sets.
6. A demo that survives a flaky API.

## 5. Non-Goals

- Detecting arbitrary logical contradictions (see section 17 for the exact scope).
- Automatic conflict resolution or deciding which document "wins".
- Numeric confidence percentages.
- Auth, multi-user, billing, production hardening, large corpora (design target: ≤ 20 documents, ≤ 500 chunks per investigation).
- Microservices, queues, managed vector DBs, Postgres, orchestration frameworks (LangChain etc.).

## 6. Hackathon Constraints

Solo developer · 10:00–22:00 build, submit by 23:00 · free LLM tier with request caps and variable model behaviour · Windows dev machine · judged on Functionality 25, Innovation 20, Problem Understanding 20, UI/UX 15, Impact 10, Presentation 10.

## 7. Functional Requirements Summary

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Create / return to an investigation workspace | P0 |
| FR-02 | Upload multiple documents with per-document status | P0 |
| FR-03 | PDF, TXT, DOCX, images (OCR) — only tested formats claimed | P0 |
| FR-04/05 | Extraction with location metadata; chunk, embed, index | P0 |
| FR-06 | Natural-language Q&A | P0 |
| FR-07 | Source / page / section / quote references, verified | P0 |
| FR-08 | Conflict detection on comparable claims | P0 |
| FR-09 | Evidence state: HIGH / MEDIUM / LOW / CONFLICT / INSUFFICIENT | P0 |
| FR-10 | Cross-document reasoning | P0 |
| FR-11..14 | Evidence panel, Why this answer?, contradiction map, history | P1 |
| FR-15/16 | Timeline, relationship graph | P2 |

## 8. Non-Functional Requirements Summary

Reliability of the core path · grounding (nothing fabricated) · explainability without chain-of-thought · usable without RAG vocabulary · failure isolation · **LLM frugality** (one call per question, cached) · **provider independence** (model swap by config).

---

## 9. Architecture Overview

One Python process serves the API and the built SPA. All state is one SQLite file plus an uploads folder. Embeddings, keyword search, OCR, verification, conflict and uncertainty logic all run locally with no network. The only external dependency is the LLM, reached through one adapter, used once per uncached question.

## 10. Architecture Diagram

```text
React SPA (Documents | Investigation | Evidence)
        │ HTTP/JSON
        ▼
FastAPI (single process)
  ├─ Ingestion:  validate → extract → local OCR → clean → chunk → embed → store
  ├─ Investigation Engine
  │     ├─ Retrieval            (local: embeddings + BM25)
  │     ├─ Evidence Analysis    (the one LLM call)
  │     ├─ Verification         (code)
  │     ├─ Conflict Engine      (code)
  │     ├─ Uncertainty Engine   (code)
  │     └─ Answer Composition   (code, from verified claims)
  ├─ Run cache
  └─ LLM Adapter ──► OpenRouter ──► configurable model
        ▼
SQLite + ./data/uploads
```

## 11. Component Responsibilities

| Component | Does | Does not |
|---|---|---|
| Ingestion | Produces located, embedded chunks; reports per-document status | Call the LLM (by default) |
| Retriever | Returns top evidence with every relevant document represented | Decide relevance finally |
| Evidence analyst | Interprets evidence: aspects, typed claims, verbatim quotes, draft answer sentences | Decide state, write locations |
| Verifier | Confirms quotes exist in the cited chunk; drops what fails | Trust the model |
| Conflict engine | Normalises typed values, groups positions, flags conflicts | Pick a winner |
| Uncertainty engine | Maps signals to a state and reasons | Use model self-confidence |
| Composer | Assembles the answer from verified material | Add new facts |
| LLM adapter | One interface, retries, JSON repair, replay/mock modes | Leak provider details upward |
| Run cache | Returns stored results for identical question + document set | — |

## 12. Data Flow

**Ingestion:** file → validation → pages of text (native, or OCR) → cleaned paragraphs → page-bounded chunks with location → embeddings → SQLite → status `ready`.

**Question:** question → cache lookup → hybrid retrieval → evidence items E1..En → one LLM call → claims + draft sentences → quote verification → conflict grouping → state rules → answer assembly → stored run → UI.

Traceability chain kept throughout: **Answer → Claim → Evidence → Chunk → Page/Section → Document.**

---

## 13. Document Ingestion Architecture

- **Validate**: extension allow-list, magic bytes, 20 MB per file, 10 files per upload, stored under a UUID name. SHA-256 of content; an identical file already in the investigation is marked `duplicate` and not re-indexed.
- **Extract**: PDF via PyMuPDF (text blocks per page, font sizes for headings). DOCX via python-docx (heading styles; location = section + paragraph, no invented page numbers). TXT by paragraph.
- **OCR**: see section 22.
- **Clean**: de-hyphenate line breaks, collapse whitespace, drop headers/footers that repeat across pages.
- **Chunk**: paragraph-aware, ~800 characters target, one paragraph overlap, **never across a page boundary**, so a page citation is always exact. Section = nearest preceding detected heading, else empty. Never guessed.
- **Embed**: local `fastembed` model; stored with the chunk.
- **Execution**: in-process background task per document. Status `queued → extracting → indexing → ready | failed | duplicate` with an error message. The UI polls. One failure never blocks other documents.

## 14. Retrieval Architecture

- Scope always filtered by investigation.
- Dense (cosine over NumPy array) and BM25, merged by reciprocal rank fusion.
- **Per-document diversity**: the best chunk of every document with any hit is guaranteed a slot, then fill to k = 10 by fused rank. This is what lets a minority document that disagrees reach the analyst.
- No reranker; the analyst judges relevance per item.
- No similarity threshold for "insufficient"; that is decided by zero verified claims.
- Evidence items are passed with ids `E1..En`. The model refers only to ids; locations are attached by the server from the database.
- Context is small (~3k tokens), safe for free models with modest context windows.

## 15. Investigation Engine

Fixed sequence, one orchestrator function, each stage logged and individually fallible:

1. Cache lookup
2. Retrieve
3. Analyse evidence (LLM, one call)
4. Verify quotes
5. Detect conflicts
6. Evaluate uncertainty
7. Compose answer
8. Persist run

**What the single LLM call returns** (shape, not final schema):
- `aspects` — the parts of the question (this is what makes cross-document questions work: "terms after the amendment" and "what the invoice says" become two aspects with claims from different documents).
- `claims` — each with aspect, evidence id, **verbatim quote**, normalised value, value type, scope/condition, explicit vs inferred.
- `supersession_notes` — only when a document explicitly says it replaces or amends another, with a quote.
- `answer_sentences` — draft sentences, each listing the claim ids it rests on.
- `ambiguous` — flag plus the alternative readings, if the question can be read two ways.

**Why one call, not two:** on a free tier every call is scarce and slow. Grounding is preserved because the draft answer is filtered by code after verification (section 19), not trusted as written.

## 16. Evidence Verification

- Each claim's quote must appear in the chunk it cites: whitespace- and case-normalised substring match. For OCR chunks, fuzzy match with a high threshold.
- A claim that fails is dropped and counted. It cannot appear in the answer, the conflict map or the signals.
- Evidence ids not in the retrieved set are rejected.
- Document name, page and section shown to the user are read from the database by chunk id. The model never supplies them.
- Supersession notes are verified the same way; unverified notes are discarded.

## 17. Conflict Detection

**Scope — stated explicitly.** The MVP detects disagreement between **comparable claims on the same aspect and scope**: durations, dates, numbers, quantities, currency amounts, percentages, explicit yes/no positions, and short clearly-stated textual alternatives (e.g. governing law: "Delaware" vs "New York"). It does **not** claim to detect arbitrary logical contradictions, implied inconsistencies, or conflicts that need multi-step inference.

**Mechanism**
1. Group verified claims by aspect.
2. Normalise values by type in code: "thirty days", "net 30", "30 days" → one duration; currency and date formats likewise; yes/no synonyms to boolean.
3. Within an aspect, distinct normalised values form **positions**, each holding its claims and documents.
4. An aspect is in conflict when it has ≥ 2 positions whose scopes are the same or unspecified.

**False-conflict controls**
- Different scopes ("domestic" vs "export") → complementary, not conflicting.
- Typed values are compared by code, so wording differences cannot create a conflict.
- Duplicate documents (same file hash or identical chunk text) count as one source.
- Only verified claims participate.
- Text-type alternatives depend on the model's value normalisation; these are labelled as such in "Why this answer?" (weaker basis than typed comparison).

**Supersession.** Never resolved silently. If a verified, explicit supersession statement exists, the conflict is still shown with both positions, and a cited note is attached ("Amendment states it replaces clause 4.2"). Without explicit evidence, the conflict stands as is. The system never picks a side.

**Output to UI**: aspect → positions → documents with page. This structure is the contradiction map.

## 18. Uncertainty Engine

Fully deterministic. First matching rule wins. No percentages.

| State | Rule |
|---|---|
| INSUFFICIENT | No verified claim addresses the question, or no ready documents |
| CONFLICT | Any aspect in conflict |
| HIGH | Every aspect covered by explicit claims; main position supported by ≥ 2 independent documents; not OCR-only low-quality evidence; not ambiguous |
| MEDIUM | Every aspect covered by explicit claims, but an aspect rests on a single document |
| LOW | Any of: only inferred claims; only low-quality OCR evidence; some aspects uncovered; question flagged ambiguous; degraded mode |

Signals: verified claim count, independent document count, agreeing documents per position, conflict presence, explicit vs inferred, OCR quality, aspect coverage, ambiguity, claims dropped by the verifier. The reasons list is produced from templates over these signals and **is** the "Why this answer?" content. The model's own confidence is never requested or used.

## 19. Answer Composition

Done in code, no second LLM call.
- Keep a draft sentence only if it cites ≥ 1 claim and **all** its cited claims were verified. Sentences with no claim ids are removed.
- CONFLICT: the headline is a template ("The documents disagree on {aspect}: {position A} ({docs}) vs {position B} ({docs})"), followed by surviving sentences.
- INSUFFICIENT: fixed message; draft sentences are discarded; nearest passages are shown labelled "related, but does not answer the question".
- If no draft sentences survive but verified claims exist: a template lists the claims with citations.
- Citation markers map to claim ids → evidence.

## 20. LLM Provider Architecture

- One adapter with one job: "given instructions and a described JSON shape, return a validated object or a typed error".
- The investigation engine knows nothing about OpenRouter, HTTP, model names or JSON-mode quirks.
- Configuration: `LLM_PROVIDER`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODELS`, `LLM_MODE` (`live | replay | mock`), timeout, capability flags (`LLM_SUPPORTS_JSON_MODE`, `LLM_SUPPORTS_VISION`).
- **Replay mode**: live responses are recorded to disk keyed by prompt hash. Development of the verifier, conflict engine, uncertainty rules and all UI runs against recordings and consumes no quota.
- Adding another provider (including a local model) is a second adapter implementation, no engine change.

## 21. OpenRouter Integration Strategy

- OpenAI-compatible chat completions endpoint, called with plain HTTP. No SDK dependency.
- **Model**: default `openrouter/free`; at Checkpoint 1, smoke-test a few currently available free models against the analyst task and pin the best one in `.env`. Pinning is preferred because a router can pick a different model per request and behaviour would vary. No model id is hard-coded in the engine.
- **Structured output without relying on model support**: the JSON shape is described in the prompt; JSON mode is requested only if the capability flag is on. The response is parsed tolerantly (strip code fences, take the outermost JSON object), validated, and on failure retried once with the validation error. Still failing → degraded mode.
- **Rate limits**: calls are serialised with a minimum gap; on HTTP 429 honour `Retry-After` once, then try the fallback model list, then degrade. No retry loops.
- **Budget**: free tiers have per-minute and per-day request caps (last known: about 20/min, and a low daily cap that is much higher once the account holds a small credit balance — **check the dashboard at 10:00**). One call per question + run cache + replay mode keeps the whole day well inside a low cap. Keeping a second API key or a small credit balance ready is the cheapest insurance.
- **Run cache**: key = document-set hashes + normalised question + model + prompt version. Repeat questions, and the whole rehearsed demo, are served with no network.

## 22. OCR Strategy

- **Primary: local OCR** with `rapidocr-onnxruntime` — pip-only, no system binary to install on Windows, shares the ONNX runtime already needed for embeddings, and returns per-line confidence.
- **Trigger**: image uploads, and any PDF page with almost no text layer (page rendered by PyMuPDF, then OCR'd).
- **Quality signal**: mean OCR confidence stored per chunk. Chunks are tagged `ocr`; below a threshold they are `ocr_low`. This feeds verification (fuzzy match) and uncertainty (OCR-only → not HIGH; low-quality only → LOW), and is shown on the evidence card as "from scanned image".
- **Optional fallback**: LLM vision transcription, off by default, used only if `LLM_SUPPORTS_VISION` is set. Nothing in the demo depends on it.
- **If OCR fails**: that document is `failed` with a clear message; everything else continues.

## 23. Data Storage Strategy

| Store | Holds |
|---|---|
| SQLite `investigations` | id, title, created time |
| SQLite `documents` | investigation, filename, type, hash, status, error, page count, extraction method |
| SQLite `chunks` | document, page, section, paragraph index, char offsets, text, extraction method, OCR confidence, embedding |
| SQLite `runs` | investigation, question, state, full result as JSON, cache key, model, latency |
| `./data/uploads` | original files under UUID names |
| `./data/llm_recordings` | replay fixtures and recent raw LLM exchanges |

Claims, positions and reasons live inside the run JSON; nothing in P0/P1 needs them as separate tables. The in-memory search index is rebuilt per investigation from SQLite on demand. Exact schema is deferred to LLD.

## 24. API Boundary

| Endpoint | Responsibility | Priority |
|---|---|---|
| Create investigation / get investigation | Workspace identity and summary | P0 |
| Upload documents (multi-file) | Validate, store, start processing; per-file accept/reject | P0 |
| List documents | Status polling | P0 |
| Ask question | Run the engine; return the investigation result | P0 |
| List runs | History | P0 (data) / P1 (UI) |
| Get chunk with neighbours | Evidence inspection | P1 |
| Page image with quote highlighted | Visual proof for PDFs | P1 |
| Seed demo set A / set B | One-click load of bundled documents | P0 |
| Health | Liveness, model, embedder/OCR status, LLM mode | P0 |
| Timeline / graph | Feature-flagged | P2 |

The investigation result is the single contract between backend and frontend: question, answer sentences with citations, state, reasons, signals, aspects → positions → claims → evidence (document, page, section, quote, extraction method), warnings. Freezing this shape is the first LLD task.

## 25. Frontend Architecture

- React + Vite + TypeScript + Tailwind. TanStack Query for fetching and document-status polling. No global state library: investigation id in the URL, selected run and selected claim in component state.
- Modules: Home (create, load demo set A/B) · Workspace shell · Documents pane (dropzone, status list) · Investigation pane (question bar, run cards, state badge, answer with citations, contradiction map, Why panel, history) · Evidence pane (evidence cards, page viewer).
- Contradiction map is a hand-built two-level tree. No graph library unless P2 is reached.
- Progress while a question runs: stepped indicator over a plain request. No streaming.

## 26. UX / Investigation Workspace

```text
┌ Investigation: Vendor Contract Review ───────────────────────────────┐
│ DOCUMENTS      │ INVESTIGATION                  │ EVIDENCE           │
│ Contract  ✓    │ Q: Are payment terms consistent│ 30 days            │
│ Amendment ✓    │ ⚠ CONFLICT DETECTED            │  Contract p.3 "…"  │
│ Invoice   ✓scan│ The documents disagree on …[1] │  Amendment p.1 "…" │
│ Policy    ✓    │ [contradiction map]            │ 45 days            │
│ bad.pdf   ✗    │ ▸ Why this answer?             │  Invoice (scan) "…"│
├────────────────┴────────────────────────────────┴────────────────────┤
│ Ask a question about these documents…                                │
└──────────────────────────────────────────────────────────────────────┘
```

- Each run is a card: question → state badge with one-line reason → answer with numbered citations → contradiction map (only on conflict) → collapsible "Why this answer?".
- Clicking a citation highlights its evidence card; "view page" shows the PDF page with the quote boxed.
- States use colour + icon + words, never a percentage.
- Empty states: no documents (question bar disabled with a hint), still processing, failed document with its reason.
- P0 version of this screen: the same three columns, with evidence as a plain list under the answer. P1 makes it the polished panel.

## 27. Failure Handling

| Failure | Behaviour |
|---|---|
| Unsupported / oversized file | Rejected with reason; others proceed |
| Extraction or OCR fails | Document `failed` with message; others unaffected |
| Embedder unavailable | BM25-only retrieval, warning in health |
| No ready documents / no verified claims | INSUFFICIENT, no fabricated answer |
| LLM returns invalid JSON | One repair retry, then evidence-only mode |
| LLM 429 / timeout / outage | One retry → fallback model → cached run if present → **evidence-only mode** |
| Evidence-only mode | Top retrieved passages shown with locations, state LOW, warning "automatic analysis unavailable" |
| Conflict step throws | Answer returned, state capped at MEDIUM, warning shown |
| P1/P2 feature fails | Its panel shows "unavailable"; core unaffected |

## 28. Security Considerations

API key server-side only · extension + magic-byte + size + count validation · UUID filenames · uploaded files parsed, never executed · document text delimited and declared untrusted in the system instructions · model output validated against the expected shape · quotes and citations verified server-side, so injected text cannot create a citation or alter the state rules · no auth; investigations addressed by unguessable id · README states documents are sent to a third-party model and that only synthetic demo documents should be used.

## 29. Observability

One structured log line per stage carrying investigation id, document id or run id, stage, latency, and counts (chunks retrieved, claims extracted, claims dropped, positions, final state), plus LLM model, status and errors. A debug flag on the question endpoint returns retrieval scores and the raw analyst output. Raw LLM exchanges are kept on disk. Nothing more.

## 30. Deployment Architecture

- **Primary (demo)**: local, one command, one port — FastAPI serving API and built SPA. Both demo sets pre-seeded, demo questions pre-run so they are cached.
- **Shareable link (if required by submission)**: tunnel to the local server. A container deploy to a free host is attempted only after Checkpoint 8 with time to spare.
- **Backup**: screen recording of the full demo.

---

## 31. P0 / P1 / P2 Feature Prioritization

**P0 — must work:** investigation creation · multi-document upload with status · PDF/TXT/DOCX/image · extraction · local OCR · chunking · indexing · retrieval · Q&A · verified source references · conflict detection · uncertainty states · cross-document reasoning · basic three-column workspace · run cache · evidence-only fallback · second document set.

**P1:** polished evidence panel · Why this answer? panel · contradiction map · history UI · page image with highlighted quote · visual polish.

**P2 — only if everything above is stable:** timeline · relationship graph · animations · LLM vision OCR fallback · hosted deployment.

Rule: P1 work does not start before Checkpoint 6 passes. P2 work does not start before Checkpoint 8 passes. Both are separate UI modules reading the run result; removing them changes nothing in P0.

## 32. Solo 12-Hour Implementation Strategy

Sequential stages for one developer. Each checkpoint has an exit test and a cut rule.

| Time | Checkpoint | Exit test | If late |
|---|---|---|---|
| 10:00–10:40 | **1 Project boots** | Backend health + blank SPA; OpenRouter smoke test returns valid JSON; model pinned; quota checked | Use `openrouter/free` unpinned |
| 10:40–12:00 | **2 Upload → extract → index** | PDF/TXT/DOCX upload, chunks with page numbers in SQLite, embeddings stored | Drop DOCX to later; BM25-only |
| 12:00–13:30 | **3 Question → answer → citation** | Ask on set A; verified quotes with document + page on screen (plain UI). Record fixtures; switch to replay mode | Skip draft sentences; template answer from claims |
| 13:30–14:00 | Break + buffer | — | — |
| 14:00–15:15 | **4 Conflict detection** | Set A consistency question → two positions, correct documents | Support duration/number/money/boolean only |
| 15:15–16:00 | **5 Uncertainty + fallbacks** | All five states reachable; LLM-off gives evidence-only mode; run cache works | Keep rules, defer cache |
| 16:00–16:40 | OCR path | Scanned image in set A indexed with OCR tag | Replace scan with text PDF; note OCR as limited |
| 16:40–17:20 | **6 Second document set** | Acceptance script green on sets A and B | Fix generalisation before any P1 work |
| 17:20–19:30 | **7 Evidence UI, Why, Contradiction map** | Full demo path looks finished; history list | Cut page-image viewer first, then history |
| 19:30–20:15 | **8 Deploy / README / pre-run demo** | Fresh-clone run works; demo runs cached | Local only, no tunnel |
| 20:15 | **9 Feature freeze** | Bug fixes only from here | — |
| 20:15–21:30 | **10 Rehearsal + backup** | Three clean run-throughs; video recorded | — |
| 21:30–22:00 | Submit | Submission made, 1 hour of slack remains | — |

First working end-to-end path: 13:30. Demo documents for both sets are prepared as synthetic files during Checkpoints 2 and 6 (short, 2–4 pages each, so page citations are real).

## 33. Demo Strategy

1. Create investigation, load set A (contract, amendment, scanned invoice, policy) — show processing statuses, including the "scan" tag.
2. "What are the late payment penalties?" → grounded answer, state shown → click citation → page, section, quote.
3. Cross-document: "What payment terms apply after the amendment, and does the invoice follow them?" → evidence from three documents.
4. "Are the payment terms consistent across the documents?" → **CONFLICT DETECTED** → competing claims → contradiction map → sources.
5. Open "Why this answer?" → sources, agreement, quality, reason. State that the system does not choose a side.
6. Ask something not in the documents → INSUFFICIENT EVIDENCE.
7. Switch to set B (unrelated domain) → one question, one conflict of a different value type. "Nothing here is hard-coded."
8. Closing line: the four-sentence principle from section 1.

All demo questions are pre-run, so the demo holds even with no network; one live uncached question is asked if the API is healthy.

## 34. Acceptance Criteria

| Test | Pass condition |
|---|---|
| A Normal question | Correct answer, ≥ 1 citation, every quote found in its chunk |
| B Cross-document | Claims cited from ≥ 2 documents |
| C Conflict | State CONFLICT, both positions with correct documents, no winner chosen |
| D Missing information | State INSUFFICIENT, no composed answer |
| E Why this answer? | Non-empty reasons and signals, no model reasoning text |
| F Grounding | No displayed document name, page, section or quote that is absent from the database |
| G Failure isolation | A corrupt file fails alone; LLM off → evidence-only mode, no crash |
| **H Second document set (mandatory)** | Tests A, C and D pass on set B with no code or prompt change |

## 35. Testing Strategy

- One acceptance script that drives the API over both seeded sets and asserts tests A–H. Run at every checkpoint from 3 onward, in replay mode by default and live once before freeze.
- Small focused checks for the pure-code parts where bugs are cheap to catch: value normalisation, quote matching, state rules.
- Manual click-through of every citation before freeze.
- No UI test framework.

## 36. Second Document Set Validation

- **Set A — vendor contract** (contract, amendment, scanned invoice, policy): duration conflict (30 vs 45 days), money and date facts, one explicit amendment clause.
- **Set B — unrelated domain, HR** (employee handbook PDF, offer letter DOCX, HR memo TXT or scan): quantity conflict (annual leave days), a yes/no conflict (remote work permitted), a fact present in only one document (MEDIUM), a question with no answer (INSUFFICIENT).
- Set B is authored **after** the engine works on set A and is not used to tune prompts. Any fix needed for set B must be a general fix, then set A is re-run.
- Both sets ship in the repository with seed buttons, so judges can run either.

## 37. Traceability Matrix

| Requirement | Component | Workflow | Priority |
|---|---|---|---|
| Investigation workspace | Investigation API, workspace shell | Create / return | P0 |
| Multiple documents + status | Upload API, background ingestion, documents pane | Upload | P0 |
| Formats | Extractors, local OCR | Ingestion | P0 |
| Extraction with locations | Extractor, page-bounded chunker | Ingestion | P0 |
| Indexing | Local embedder, BM25, SQLite | Ingestion | P0 |
| Natural-language Q&A | Orchestrator, analyst, composer | Investigation | P0 |
| Source references | Verifier, DB-sourced locations | Investigation | P0 |
| Conflict detection | Analyst (typed claims) + conflict engine | Investigation | P0 |
| Uncertainty | Uncertainty engine rule table | Investigation | P0 |
| Cross-document reasoning | Aspect decomposition, per-document retrieval diversity | Investigation | P0 |
| No fabrication | Verifier, composer filter, ID-only references | Every answer | P0 |
| LLM resilience | Adapter, run cache, evidence-only mode | Every answer | P0 |
| Generalisation | Set B + acceptance test H | Validation | P0 |
| Evidence panel | Evidence pane, chunk/page endpoints | Verification | P1 |
| Why this answer? | Signals + reason templates, Why panel | Verification | P1 |
| Contradiction map | Positions structure, tree component | Conflict | P1 |
| History | Runs table, history list | Investigation | P1 |
| Timeline / graph | Flagged modules over stored runs | Investigation | P2 |

## 38. Technical Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Free daily quota exhausted during development | Replay mode after Checkpoint 3; one call per question; run cache; check quota at 10:00; spare key or small credit |
| Free model produces poor or malformed JSON | Tolerant parsing + one repair retry; model chosen by smoke test; fallback model list; template answers |
| Model removed or throttled on the day | Config-only switch; fallback list; cached demo |
| Model paraphrases instead of quoting, so claims get dropped | Instructions demand exact copy; light normalisation in matching; dropped-claim count logged to spot it early |
| False conflicts | Scope check, typed normalisation, duplicate collapse |
| Missed conflicts (document not retrieved) | Per-document diversity in retrieval |
| OCR quality or install trouble | pip-only OCR; quality signal lowers state instead of failing; scan replaceable with text PDF |
| Solo time overrun | Cut rules per checkpoint; P1 gated behind Checkpoint 6; freeze at 20:15 |
| Network down at demo | Cached runs, local server, recorded video |
| First-run model download for embeddings/OCR | Downloaded during Checkpoint 2, never at demo time |

## 39. Final Architecture Decision Record

| # | Decision | Reason |
|---|---|---|
| 1 | Single FastAPI process serving API and SPA | One thing to run and debug |
| 2 | SQLite + NumPy brute-force vectors + BM25 | No infrastructure; ample at this scale |
| 3 | Local embeddings (`fastembed`) | No API quota spent on indexing |
| 4 | Local OCR (`rapidocr-onnxruntime`); LLM vision optional | Demo independent of model capabilities |
| 5 | OpenRouter behind a provider adapter; model from config | Free tier, swappable |
| 6 | One LLM call per question; composition in code | Quota, latency, fewer failure points |
| 7 | Quote verification before anything is shown | Grounding is enforced, not requested |
| 8 | Conflict detection on typed comparable claims, in code | Deterministic and explainable; honest scope |
| 9 | Conflicts never auto-resolved; supersession shown as a cited note | Core product thesis |
| 10 | Rule-table uncertainty, no percentages | Explainable, not decorative |
| 11 | Run cache + replay/mock LLM modes | Demo and development survive API limits |
| 12 | Evidence-only degraded mode | App never depends on one successful LLM call |
| 13 | Three-pane workspace, hand-built contradiction tree | Shows the innovation without a graph library |
| 14 | Two bundled document sets, acceptance script | Proves generalisation |
| 15 | No auth, queue, container requirement or hosted deploy in P0 | Solo time budget |

## 40. HLD Freeze Checklist

| # | Review question | Answer |
|---|---|---|
| 1 | Buildable solo in 12 h? | Yes — P0 ends 17:20 with cut rules |
| 2 | Early end-to-end path? | Yes — 13:30 |
| 3 | Over-dependent on free API? | No — one call per question, cache, replay, evidence-only mode |
| 4 | Model/provider swappable? | Yes — config + adapter |
| 5 | Works with limited OCR/model capability? | Yes — local OCR, no JSON-mode or vision assumed |
| 6 | Handles rate limits? | Yes — serialised calls, one retry, fallback models, cache |
| 7 | Handles LLM failure? | Yes — evidence-only mode |
| 8 | Citations verifiable? | Yes — server-side quote match, DB-sourced locations |
| 9 | Conflict detection deterministic where possible? | Yes — typed comparison in code |
| 10 | Uncertainty deterministic? | Yes — rule table |
| 11 | Cross-document reasoning? | Yes — aspects + per-document retrieval |
| 12 | Second unrelated set? | Yes — mandatory test H |
| 13 | Simple to debug? | Yes — linear stages, per-stage logs, debug flag |
| 14 | Distinct from generic RAG? | Yes — verify / compare / evaluate stages are code |
| 15 | UI shows the innovation? | Yes — state badge, contradiction map, Why panel |
| 16 | P1/P2 cannot endanger P0? | Yes — gated by checkpoints, separate modules |
| 17 | Explainable to judges? | Yes — four-sentence principle |
| 18 | Demo survives unstable internet? | Yes — cached runs, local server, video |

---

## HLD STATUS: FROZEN

**B. Final architectural decisions**
- React SPA → single FastAPI process → SQLite + local files.
- Local embeddings, BM25, NumPy vector search, local OCR.
- OpenRouter via a provider adapter; model set by configuration.
- One LLM call per question: extract aspects, typed claims, verbatim quotes, draft sentences.
- Code verifies quotes, detects conflicts on comparable claims, assigns the evidence state, and assembles the answer.
- Conflicts are never auto-resolved.
- Run cache, replay mode, and evidence-only fallback.
- Two bundled document sets with an acceptance script.
- P1 gated behind Checkpoint 6, P2 behind Checkpoint 8, feature freeze at 20:15.

**C. Deferred to LLD**
- Exact investigation-result schema and database schema.
- Analyst prompt wording and the JSON shape description.
- Value-normalisation rules per type; quote-matching and OCR-quality thresholds.
- Chunk size, overlap, top-k and fusion constants.
- Heading-detection heuristics.
- Reason templates for each state.
- Endpoint paths and payloads; component breakdown and styling.
- Content of document sets A and B; the pinned model and fallback list.
- Whether an optional second "polish" LLM call is worth adding (default: no).

**D. Remaining risks to handle during implementation**
- Free-tier daily quota and model availability on the day.
- Free-model JSON reliability and exact-quote discipline.
- Scope/aspect labelling consistency across documents (drives both false and missed conflicts).
- OCR accuracy on the scanned demo file.
- Solo schedule slip in Checkpoints 3–4.
- First-run model downloads on the dev machine.

**E.** This HLD is optimized for a solo developer, a 12-hour hackathon, and an OpenRouter free-model strategy.

No implementation, LLD, schemas, prompts or code are produced in this phase. Next phase after approval: Phase 4 — LLD.
