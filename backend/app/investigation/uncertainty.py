"""Deterministic evidence state and reasons (LLD section 14). First matching rule wins. No percentages.

The model's own confidence is never requested or used: the state is a pure function of observable
evidence signals, and the reasons are fixed templates filled from those signals.
"""


def _n(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _independent_documents(claims: list[dict], text_hash: dict[str, str]) -> int:
    """Distinct documents, counting the same passage text in two files once."""
    documents = {c["evidence"]["document_id"] for c in claims}
    hashes = {text_hash.get(c["evidence"]["chunk_id"], c["evidence"]["chunk_id"]) for c in claims}
    return min(len(documents), len(hashes))


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def evaluate(
    aspects: list[dict],
    claims: list[dict],
    evidence: list[dict],
    *,
    ambiguous: bool = False,
    ambiguity_note: str | None = None,
    evidence_only: bool = False,
    conflict_check_failed: bool = False,
    has_ready_documents: bool = True,
    claims_dropped: int = 0,
) -> dict:
    """Returns {"state", "rule", "reasons"}."""
    text_hash = {item["chunk_id"]: item.get("text_hash", item["chunk_id"]) for item in evidence}
    documents = {c["evidence"]["document_id"] for c in claims}
    by_aspect = {a["id"]: [c for c in claims if c["aspect_id"] == a["id"]] for a in aspects}
    conflicting = [a for a in aspects if a["status"] == "conflict"]
    uncovered = [a for a in aspects if a["status"] == "uncovered"]

    def well_supported(aspect: dict) -> bool:
        explicit = [c for c in by_aspect[aspect["id"]] if c["explicit"]]
        return (
            _independent_documents(explicit, text_hash) >= 2
            and any(c["evidence"]["ocr_quality"] != "low" for c in explicit)
        )

    reasons: list[str] = []
    if claims:
        reasons.append(
            f'{_n(len(claims), "relevant passage")} {"was" if len(claims) == 1 else "were"} confirmed across '
            f'{_n(len(documents), "document")}.'
        )

    # --- ordered rules ---------------------------------------------------------
    if evidence_only:
        state, rule = "LOW", 1
        reasons.append("Automatic analysis was unavailable, so only the closest passages are shown.")
    elif not has_ready_documents:
        state, rule = "INSUFFICIENT", 2
        reasons.append("No processed documents are available yet.")
    elif not claims:
        state, rule = "INSUFFICIENT", 2
        reasons.append("None of the retrieved passages states an answer to this question.")
    elif conflicting:
        state, rule = "CONFLICT", 3
        for aspect in conflicting:
            sides = [f'{_n(len(p["document_ids"]), "document")} {"states" if len(p["document_ids"]) == 1 else "state"} '
                     f'{p["display"]}' for p in aspect["positions"]]
            reasons.append("; ".join(sides) + ".")
        reasons.append("Because the documents disagree, no single answer is given.")
    elif ambiguous:
        state, rule = "LOW", 4
        note = (ambiguity_note or "").strip()
        reasons.append("The question can be read in more than one way" + (f": {note}" if note else "."))
    elif uncovered:
        state, rule = "LOW", 5
        reasons.append("No evidence was found for: " + ", ".join(_lower_first(a["label"]) for a in uncovered) + ".")
    elif not any(c["explicit"] for c in claims):
        state, rule = "LOW", 6
        reasons.append("The documents do not state this directly; the answer is inferred.")
    elif all(c["evidence"]["ocr_quality"] == "low" for c in claims):
        state, rule = "LOW", 7
        reasons.append("All supporting text comes from a low-quality scan.")
    elif not conflict_check_failed and all(well_supported(a) for a in aspects):
        state, rule = "HIGH", 8
        fewest = min(_independent_documents([c for c in by_aspect[a["id"]] if c["explicit"]], text_hash) for a in aspects)
        reasons.append(f"{fewest} independent documents state the same thing directly.")
    else:
        state, rule = "MEDIUM", 9
        if conflict_check_failed:
            reasons.append("The conflict check could not be completed.")
        for aspect in aspects:
            explicit = [c for c in by_aspect[aspect["id"]] if c["explicit"]]
            if well_supported(aspect):
                continue
            names = list(dict.fromkeys(c["evidence"]["document"] for c in by_aspect[aspect["id"]]))
            if len(names) == 1:
                what = "this" if len(aspects) == 1 else _lower_first(aspect["label"])
                reasons.append(f"Only one document ({names[0]}) states {what}.")
            elif _independent_documents(explicit, text_hash) < 2:
                reasons.append(f"Only one document states {_lower_first(aspect['label'])} directly.")
            else:
                reasons.append(f"Support for {_lower_first(aspect['label'])} comes only from low-quality scans.")

    # --- additional observable signals -------------------------------------------
    for aspect in aspects:
        for note in aspect["notes"]:
            reasons.append(
                f'{note["evidence"]["document"]} states that it replaces an earlier provision; '
                "the conflict is still shown so you can decide."
                if aspect["status"] == "conflict"
                else f'{note["evidence"]["document"]} states that it replaces an earlier provision.'
            )
    ocr = sum(1 for c in claims if c["evidence"]["extraction_method"] == "ocr")
    if ocr:
        reasons.append(f'{_n(ocr, "passage")} {"comes" if ocr == 1 else "come"} from scanned images.')
    for aspect in aspects:
        if aspect["basis"] == "text" and len(aspect["positions"]) > 1:
            reasons.append(
                f"Positions on {_lower_first(aspect['label'])} were compared as text, which is less exact than "
                "numeric comparison."
            )
        if aspect["status"] == "complementary":
            scopes = list(dict.fromkeys(c["scope"] for c in by_aspect[aspect["id"]] if c["scope"]))
            reasons.append(
                "Different values apply to different conditions" + (": " + ", ".join(scopes) + "." if scopes else ".")
            )
    if claims_dropped:
        reasons.append(
            f'{_n(claims_dropped, "extracted statement")} {"was" if claims_dropped == 1 else "were"} discarded '
            "because the quote could not be found in the source."
        )
    return {"state": state, "rule": rule, "reasons": list(dict.fromkeys(reasons))}
