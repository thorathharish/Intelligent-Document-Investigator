"""run_investigation: retrieve -> analyse (one LLM call) -> verify -> compose -> persist (LLD section 16).

Conflict detection, the uncertainty rules and the run cache are added in Checkpoints 4 and 5.
"""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

from .. import db
from ..config import settings
from ..llm import LLMBadOutput, LLMUnavailable
from ..logging_utils import log_stage
from ..retrieval import retriever
from . import analyst, composer, verifier


def _cache_key(question: str, document_hashes: list[str]) -> str:
    raw = "|".join([settings.prompt_version, settings.openrouter_model, ",".join(sorted(document_hashes)), question.lower()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def run_investigation(investigation_id: str, question: str, fresh: bool = False, debug: bool = False) -> dict:
    started = time.monotonic()
    run_id = str(uuid.uuid4())
    question = " ".join(question.split())
    ready = db.query(
        "SELECT sha256 FROM documents WHERE investigation_id = ? AND status = 'ready'", (investigation_id,)
    )
    cache_key = _cache_key(question, [row["sha256"] for row in ready])

    evidence: list[dict] = []
    degraded = False
    model = None
    raw_output = None
    dropped: list[dict] = []
    timings: dict[str, int] = {}

    if not ready:
        body = composer.compose_no_documents()
    else:
        t = time.monotonic()
        evidence = retriever.retrieve(investigation_id, question)
        timings["retrieve"] = int((time.monotonic() - t) * 1000)
        log_stage("retrieve", run=run_id, inv=investigation_id, ms=timings["retrieve"], evidence=len(evidence),
                  docs=len({e["document_id"] for e in evidence}))
        try:
            t = time.monotonic()
            result = analyst.analyse(question, evidence)
            timings["analyse"] = int((time.monotonic() - t) * 1000)
            model, output = result.model, result.value
            raw_output = output.model_dump()
            log_stage("analyse", run=run_id, model=model, ms=timings["analyse"], recording=result.from_recording,
                      aspects=len(output.aspects), claims=len(output.claims))

            verification = verifier.verify(output, evidence)
            dropped = verification["dropped"]
            reasons = ",".join(sorted({d["reason"] for d in dropped})) or None
            log_stage("verify", run=run_id, verified=len(verification["claims"]), dropped=len(dropped), reasons=reasons)

            body = composer.compose(output, verification, evidence)
        except (LLMUnavailable, LLMBadOutput) as exc:
            degraded = True
            log_stage("analyse", level="WARN", run=run_id, error=type(exc).__name__, detail=str(exc)[:200])
            body = composer.compose_evidence_only(evidence)

    latency_ms = int((time.monotonic() - started) * 1000)
    created_at = datetime.now(timezone.utc).isoformat()
    result_json = {
        "run_id": run_id,
        "investigation_id": investigation_id,
        "question": question,
        "created_at": created_at,
        "state": body["state"],
        "headline": body["headline"],
        "degraded": degraded,
        "cached": False,
        "answer": body["answer"],
        "aspects": body["aspects"],
        "claims": body["claims"],
        "signals": body["signals"],
        "reasons": body["reasons"],
        "related": body["related"],
        "warnings": body["warnings"],
        "debug": None,
    }
    log_stage("state", run=run_id, state=body["state"], degraded=degraded, ms=latency_ms)

    db.execute(
        "INSERT INTO runs (id, investigation_id, question, cache_key, state, degraded, result_json, model,"
        " latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, investigation_id, question, cache_key, body["state"], int(degraded),
         json.dumps(result_json, ensure_ascii=False), model, latency_ms, created_at),
    )

    if debug:
        result_json = dict(result_json)
        result_json["debug"] = {
            "evidence": [
                {k: e[k] for k in ("eid", "chunk_id", "document", "page", "fused_score", "dense_rank", "bm25_rank")}
                for e in evidence
            ],
            "analyst_output": raw_output,
            "dropped_claims": dropped,
            "timings_ms": timings,
            "model": model,
        }
    return result_json
