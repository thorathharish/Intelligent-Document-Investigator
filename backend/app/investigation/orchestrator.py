"""run_investigation (LLD section 16):

cache lookup -> retrieve -> analyse (one LLM call) -> verify -> detect conflicts -> evaluate state
-> compose -> persist.
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
from ..schemas import AnalystOutput
from . import analyst, composer, conflicts, verifier


def cache_key(question: str, document_hashes: list[str]) -> str:
    """Prompt version + model + document set + normalised question (LLD section 16)."""
    normalised = " ".join(question.lower().split())
    raw = "|".join([settings.prompt_version, settings.openrouter_model, ",".join(sorted(document_hashes)), normalised])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cached_result(investigation_id: str, key: str) -> dict | None:
    # degraded runs (evidence-only, or conflict check failed) are stored for history but never served
    row = db.query_one(
        "SELECT result_json FROM runs WHERE investigation_id = ? AND cache_key = ? AND degraded = 0"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (investigation_id, key),
    )
    if row is None:
        return None
    result = json.loads(row["result_json"])
    result["cached"] = True
    return result


def run_investigation(investigation_id: str, question: str, fresh: bool = False, debug: bool = False) -> dict:
    started = time.monotonic()
    run_id = str(uuid.uuid4())
    question = " ".join(question.split())
    ready = db.query(
        "SELECT sha256 FROM documents WHERE investigation_id = ? AND status = 'ready'", (investigation_id,)
    )
    key = cache_key(question, [row["sha256"] for row in ready])

    if ready and not fresh:
        cached = _cached_result(investigation_id, key)
        if cached is not None:
            log_stage("cache", run=cached["run_id"], inv=investigation_id, hit=True,
                      ms=int((time.monotonic() - started) * 1000))
            return cached

    evidence: list[dict] = []
    evidence_only = False
    conflict_check_failed = False
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
        if not evidence:
            body = composer.compose(AnalystOutput(), {"claims": [], "dropped": [], "notes": []}, [], [], llm_source="none")
        else:
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
                log_stage("verify", run=run_id, verified=len(verification["claims"]), dropped=len(dropped),
                          reasons=reasons)

                try:
                    aspects = conflicts.detect(output.aspects, verification["claims"], evidence, verification["notes"])
                except Exception as exc:  # the answer is still returned, without conflict analysis
                    conflict_check_failed = True
                    aspects = conflicts.fallback(output.aspects, verification["claims"])
                    log_stage("conflict", level="WARN", run=run_id, error=f"{type(exc).__name__}: {exc}"[:200])
                log_stage("conflict", run=run_id, aspects=len(aspects),
                          conflicting=sum(a["status"] == "conflict" for a in aspects),
                          positions=sum(len(a["positions"]) for a in aspects))

                body = composer.compose(output, verification, evidence, aspects, conflict_check_failed,
                                        llm_source="recording" if result.from_recording else "live")
            except (LLMUnavailable, LLMBadOutput) as exc:
                evidence_only = True
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
        "degraded": evidence_only,
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
    log_stage("state", run=run_id, state=body["state"], rule=body["rule"], degraded=evidence_only,
              conflict_check_failed=conflict_check_failed, ms=latency_ms)

    # the degraded column also covers a failed conflict check, so such runs are never served from cache
    not_cacheable = evidence_only or conflict_check_failed
    db.execute(
        "INSERT INTO runs (id, investigation_id, question, cache_key, state, degraded, result_json, model,"
        " latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, investigation_id, question, key, body["state"], int(not_cacheable),
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
            "rule": body["rule"],
        }
    return result_json
