"""Answer composition in code, from verified claims only (LLD section 15).

Checkpoint 3 version: the state is provisional (INSUFFICIENT or MEDIUM). Conflict positions, the full
uncertainty rules and reason templates arrive in Checkpoints 4 and 5.
"""
from ..ingestion.ocr import OCR_LOW_THRESHOLD
from ..schemas import AnalystOutput

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


def _signals(evidence: list[dict], extracted: int, claims: list[dict], dropped: int, aspects: list[dict], ambiguous: bool) -> dict:
    return {
        "evidence_retrieved": len(evidence),
        "claims_extracted": extracted,
        "claims_verified": len(claims),
        "claims_dropped": dropped,
        "documents_cited": len({c["evidence"]["document_id"] for c in claims}),
        "aspects_total": len(aspects),
        "aspects_covered": sum(1 for a in aspects if a["status"] != "uncovered"),
        "conflicting_aspects": 0,
        "explicit_claims": sum(1 for c in claims if c["explicit"]),
        "ocr_claims": sum(1 for c in claims if c["evidence"]["extraction_method"] == "ocr"),
        "ocr_low_claims": sum(1 for c in claims if c["evidence"]["ocr_quality"] == "low"),
        "ambiguous": ambiguous,
    }


def compose(output: AnalystOutput, verification: dict, evidence: list[dict]) -> dict:
    """Build the answer part of the investigation result from verified claims."""
    claims = verification["claims"]
    verified_ids = {c["id"] for c in claims}

    # keep a draft sentence only if it cites at least one claim and every cited claim was verified
    sentences = []
    for sentence in output.answer:
        text = sentence.text.strip()[:MAX_SENTENCE_CHARS]
        if text and sentence.claims and all(c in verified_ids for c in sentence.claims):
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

    aspects = []
    for aspect in output.aspects:
        covered = any(c["aspect_id"] == aspect.id for c in claims)
        aspects.append(
            {
                "id": aspect.id,
                "label": aspect.label,
                "status": "consistent" if covered else "uncovered",
                "basis": "typed",
                "positions": [],
                "notes": [],
            }
        )

    signals = _signals(evidence, len(output.claims), claims, len(verification["dropped"]), aspects, output.ambiguous)
    warnings = []
    if signals["ocr_claims"]:
        warnings.append(f'{signals["ocr_claims"]} passage(s) come from scanned images.')

    if not claims:
        return {
            "state": "INSUFFICIENT",
            "headline": INSUFFICIENT_HEADLINE,
            "answer": [],
            "aspects": aspects,
            "claims": [],
            "signals": signals,
            "reasons": ["None of the retrieved passages states an answer to this question."],
            "related": related_passages(evidence, 3),
            "warnings": warnings,
        }

    reasons = [
        f'{signals["claims_verified"]} relevant passage(s) were confirmed across '
        f'{signals["documents_cited"]} document(s).'
    ]
    if signals["claims_dropped"]:
        reasons.append(
            f'{signals["claims_dropped"]} extracted statement(s) were discarded because their quote could not '
            "be found in the source."
        )
    return {
        "state": "MEDIUM",  # provisional until the uncertainty engine (Checkpoint 5)
        "headline": sentences[0]["text"],
        "answer": sentences,
        "aspects": aspects,
        "claims": claims,
        "signals": signals,
        "reasons": reasons,
        "related": [],
        "warnings": warnings,
    }


def compose_no_documents() -> dict:
    return {
        "state": "INSUFFICIENT",
        "headline": INSUFFICIENT_HEADLINE,
        "answer": [],
        "aspects": [],
        "claims": [],
        "signals": _signals([], 0, [], 0, [], False),
        "reasons": ["No processed documents are available yet."],
        "related": [],
        "warnings": [],
    }


def compose_evidence_only(evidence: list[dict]) -> dict:
    """LLM unavailable or unusable output: show the closest passages, claim nothing."""
    return {
        "state": "LOW",
        "headline": DEGRADED_HEADLINE,
        "answer": [],
        "aspects": [],
        "claims": [],
        "signals": _signals(evidence, 0, [], 0, [], False),
        "reasons": ["Automatic analysis was unavailable, so only the closest passages are shown."],
        "related": related_passages(evidence, 5),
        "warnings": ["Automatic analysis unavailable."],
    }
