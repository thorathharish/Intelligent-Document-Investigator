"""Answer composition in code, from verified claims only (LLD section 15).

The state is CONFLICT when the conflict engine finds one, otherwise provisional (INSUFFICIENT or MEDIUM).
The full uncertainty rules and reason templates arrive in Checkpoint 5.
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


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def compose(
    output: AnalystOutput,
    verification: dict,
    evidence: list[dict],
    aspects: list[dict],
    conflict_check_failed: bool = False,
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

    signals = _signals(evidence, len(output.claims), claims, len(verification["dropped"]), aspects, output.ambiguous)
    signals["conflicting_aspects"] = len(conflicting)
    warnings = []
    if signals["ocr_claims"]:
        warnings.append(f'{signals["ocr_claims"]} passage(s) come from scanned images.')
    if conflict_check_failed:
        warnings.append("The conflict check could not be completed.")

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
    if conflicting:
        labels = [a["label"][:1].lower() + a["label"][1:] for a in conflicting]
        state, headline = "CONFLICT", f"The documents disagree on {_join(labels)}."
    else:
        # provisional until the uncertainty engine (Checkpoint 5)
        state, headline = "MEDIUM", sentences[0]["text"]
    return {
        "state": state,
        "headline": headline,
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
