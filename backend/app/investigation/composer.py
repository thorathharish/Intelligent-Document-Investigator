"""Answer composition in code, from verified claims only (LLD section 15).

The evidence state and its reasons come from the uncertainty engine; nothing here asks the model.
"""
from ..ingestion.ocr import OCR_LOW_THRESHOLD
from ..retrieval import embedder
from ..schemas import AnalystOutput
from . import uncertainty

MAX_SENTENCE_CHARS = 400
RELATED_QUOTE_CHARS = 240
INSUFFICIENT_HEADLINE = "The uploaded documents do not contain enough evidence to answer this."
DEGRADED_HEADLINE = "Automatic analysis is unavailable right now. These are the most relevant passages."


def related_passages(evidence: list[dict], limit: int) -> list[dict]:
    related = []
    for item in evidence[:limit]:
        quality = None
        if item["extraction_method"] == "ocr":
            confidence = item.get("ocr_confidence")
            quality = "low" if confidence is not None and confidence < OCR_LOW_THRESHOLD else "good"
        related.append(
            {
                "chunk_id": item["chunk_id"],
                "document_id": item["document_id"],
                "document": item["document"],
                "page": item["page"],
                "section": item["section"],
                "paragraph": item["paragraph"],
                "quote": item["text"][:RELATED_QUOTE_CHARS],
                "extraction_method": item["extraction_method"],
                "ocr_quality": quality,
            }
        )
    return related


def _signals(
    evidence: list[dict],
    extracted: int,
    claims: list[dict],
    dropped: int,
    aspects: list[dict],
    ambiguous: bool = False,
    evidence_only: bool = False,
    conflict_check_failed: bool = False,
    llm_source: str = "none",
) -> dict:
    explicit = sum(1 for c in claims if c["explicit"])
    covered = sum(1 for a in aspects if a["status"] != "uncovered")
    return {
        # LLD section 5
        "evidence_retrieved": len(evidence),
        "claims_extracted": extracted,
        "claims_verified": len(claims),
        "claims_dropped": dropped,
        "documents_cited": len({c["evidence"]["document_id"] for c in claims}),
        "aspects_total": len(aspects),
        "aspects_covered": covered,
        "conflicting_aspects": sum(1 for a in aspects if a["status"] == "conflict"),
        "explicit_claims": explicit,
        "ocr_claims": sum(1 for c in claims if c["evidence"]["extraction_method"] == "ocr"),
        "ocr_low_claims": sum(1 for c in claims if c["evidence"]["ocr_quality"] == "low"),
        "ambiguous": ambiguous,
        # additional deterministic signals
        "inferred_claims": len(claims) - explicit,
        "aspects_uncovered": len(aspects) - covered,
        "agreeing_documents": max((len(p["document_ids"]) for a in aspects for p in a["positions"]), default=0),
        "evidence_only": evidence_only,
        "conflict_check_failed": conflict_check_failed,
        "llm_source": llm_source,  # live | recording | none
    }


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _warnings(signals: dict) -> list[str]:
    warnings = []
    if signals["ocr_claims"]:
        count = signals["ocr_claims"]
        warnings.append(f'{count} passage{"" if count == 1 else "s"} {"comes" if count == 1 else "come"} from scanned images.')
    if signals["conflict_check_failed"]:
        warnings.append("The conflict check could not be completed.")
    if embedder.status() == "unavailable":
        warnings.append("Semantic search is unavailable; keyword search only.")
    return warnings


def compose(
    output: AnalystOutput,
    verification: dict,
    evidence: list[dict],
    aspects: list[dict],
    conflict_check_failed: bool = False,
    llm_source: str = "live",
) -> dict:
    """Build the answer part of the investigation result from verified claims."""
    claims = verification["claims"]
    verified_ids = {c["id"] for c in claims}
    by_id = {c["id"]: c for c in claims}
    conflicting = [a for a in aspects if a["status"] == "conflict"]
    conflict_aspect_ids = {a["id"] for a in conflicting}

    # conflicts: one generated sentence per position, naming its documents; no side is preferred
    sentences = []
    for aspect in conflicting:
        for position in aspect["positions"]:
            names = list(dict.fromkeys(by_id[cid]["evidence"]["document"] for cid in position["claim_ids"]))
            verb = "states" if len(names) == 1 else "state"
            sentences.append(
                {"text": f'{_join(names)} {verb} {position["display"]}.', "claim_ids": list(position["claim_ids"])}
            )

    # keep a draft sentence only if it cites at least one claim and every cited claim was verified;
    # draft sentences about a conflicting aspect are replaced by the generated ones above
    for sentence in output.answer:
        text = sentence.text.strip()[:MAX_SENTENCE_CHARS]
        if not (text and sentence.claims and all(c in verified_ids for c in sentence.claims)):
            continue
        if any(by_id[c]["aspect_id"] in conflict_aspect_ids for c in sentence.claims):
            continue
        sentences.append({"text": text, "claim_ids": list(dict.fromkeys(sentence.claims))})

    if claims and not sentences:
        for claim in claims:
            stated = claim["value"] if claim["position_key"] else f'"{claim["evidence"]["quote"]}"'
            sentences.append({"text": f'{claim["evidence"]["document"]} states: {stated}.', "claim_ids": [claim["id"]]})

    # citation numbers: order of first use in the answer, then the remaining verified claims
    order = list(dict.fromkeys(cid for s in sentences for cid in s["claim_ids"]))
    order += [c["id"] for c in claims if c["id"] not in order]
    numbers = {cid: n for n, cid in enumerate(order, start=1)}
    for claim in claims:
        claim["citation"] = numbers[claim["id"]]
    claims.sort(key=lambda c: c["citation"])

    not_found = sum(1 for d in verification["dropped"] if d["reason"] != "duplicate")
    signals = _signals(evidence, len(output.claims), claims, not_found, aspects, output.ambiguous,
                       conflict_check_failed=conflict_check_failed, llm_source=llm_source)
    verdict = uncertainty.evaluate(
        aspects, claims, evidence,
        ambiguous=output.ambiguous, ambiguity_note=output.ambiguity_note,
        conflict_check_failed=conflict_check_failed, claims_dropped=not_found,
    )
    state = verdict["state"]

    if state == "INSUFFICIENT":
        headline, sentences, claims, related = INSUFFICIENT_HEADLINE, [], [], related_passages(evidence, 3)
    elif state == "CONFLICT":
        labels = [a["label"][:1].lower() + a["label"][1:] for a in conflicting]
        headline, related = f"The documents disagree on {_join(labels)}.", []
    else:
        headline, related = (sentences[0]["text"] if sentences else "Here is what the documents state."), []

    return {
        "state": state,
        "headline": headline,
        "answer": sentences,
        "aspects": aspects,
        "claims": claims,
        "signals": signals,
        "reasons": verdict["reasons"],
        "related": related,
        "warnings": _warnings(signals),
        "rule": verdict["rule"],
    }


def compose_no_documents() -> dict:
    verdict = uncertainty.evaluate([], [], [], has_ready_documents=False)
    return {
        "state": verdict["state"],
        "headline": INSUFFICIENT_HEADLINE,
        "answer": [],
        "aspects": [],
        "claims": [],
        "signals": _signals([], 0, [], 0, []),
        "reasons": verdict["reasons"],
        "related": [],
        "warnings": [],
        "rule": verdict["rule"],
    }


def compose_evidence_only(evidence: list[dict]) -> dict:
    """LLM unavailable or unusable output: show the closest passages, claim nothing."""
    verdict = uncertainty.evaluate([], [], evidence, evidence_only=True)
    signals = _signals(evidence, 0, [], 0, [], evidence_only=True)
    return {
        "state": verdict["state"],
        "headline": DEGRADED_HEADLINE,
        "answer": [],
        "aspects": [],
        "claims": [],
        "signals": signals,
        "reasons": verdict["reasons"],
        "related": related_passages(evidence, 5),
        "warnings": ["Automatic analysis unavailable."] + _warnings(signals),
        "rule": verdict["rule"],
    }
