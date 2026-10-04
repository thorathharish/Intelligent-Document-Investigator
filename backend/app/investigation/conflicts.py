"""Deterministic conflict detection over verified claims (LLD section 13).

Scope: comparable values on the same aspect and scope (durations, numbers, money, percentages, dates,
yes/no, short text alternatives). No winner is ever chosen; positions only carry their supporting documents.
"""
import re
from itertools import combinations

_WS = re.compile(r"\s+")


def _label_key(label: str) -> str:
    return _WS.sub(" ", re.sub(r"[^\w\s]", " ", label.lower())).strip()


def _family(position_key: str) -> str:
    return position_key.split(":", 1)[0]


def _unit(position_key: str) -> str:
    return position_key.rsplit("|", 1)[-1] if "|" in position_key else ""


def claims_conflict(a: dict, b: dict, text_hash: dict[str, str]) -> bool:
    """Two verified claims on the same aspect conflict when all LLD conditions hold."""
    key_a, key_b = a["position_key"], b["position_key"]
    if not key_a or not key_b or key_a == key_b:
        return False
    if _family(key_a) != _family(key_b):
        return False
    if _family(key_a) == "quantity":
        unit_a, unit_b = _unit(key_a), _unit(key_b)
        if unit_a and unit_b and unit_a != unit_b:
            return False  # "1 month" vs "30 days": equivalence is not guessed, and neither is a conflict
    # one passage listing several values is treated as conditional, not contradictory
    chunk_a, chunk_b = a["evidence"]["chunk_id"], b["evidence"]["chunk_id"]
    if chunk_a == chunk_b or text_hash.get(chunk_a, chunk_a) == text_hash.get(chunk_b, chunk_b):
        return False
    # scopes must be compatible: either is unspecified, or both are equal
    if a["scope"] and b["scope"] and a["scope"] != b["scope"]:
        return False
    return True


def detect(aspects: list, claims: list[dict], evidence: list[dict], notes: list[dict] | None = None) -> list[dict]:
    """Return result aspects with status, basis, positions and notes. Mutates claims' aspect_id when
    aspects with the same label are merged."""
    text_hash = {item["chunk_id"]: item.get("text_hash", item["chunk_id"]) for item in evidence}

    # 1. merge aspects whose normalised labels are equal
    canonical: dict[str, str] = {}
    by_label: dict[str, str] = {}
    merged = []
    for aspect in aspects:
        key = _label_key(aspect.label) or aspect.id
        if key in by_label:
            canonical[aspect.id] = by_label[key]
        else:
            by_label[key] = canonical[aspect.id] = aspect.id
            merged.append(aspect)
    for claim in claims:
        claim["aspect_id"] = canonical.get(claim["aspect_id"], claim["aspect_id"])
    for note in notes or []:
        note["aspect_id"] = canonical.get(note.get("aspect_id"), note.get("aspect_id"))

    result = []
    for aspect in merged:
        own = [c for c in claims if c["aspect_id"] == aspect.id]

        # 2. positions: comparable claims grouped by normalised key
        positions: dict[str, dict] = {}
        for claim in own:
            key = claim["position_key"]
            if not key:
                continue
            position = positions.setdefault(
                key, {"key": key, "display": claim["value"], "claim_ids": [], "document_ids": [], "_hashes": set()}
            )
            position["claim_ids"].append(claim["id"])
            # the same passage text in two files counts as one source
            digest = text_hash.get(claim["evidence"]["chunk_id"], claim["evidence"]["chunk_id"])
            if claim["evidence"]["document_id"] not in position["document_ids"] and digest not in position["_hashes"]:
                position["document_ids"].append(claim["evidence"]["document_id"])
            position["_hashes"].add(digest)

        # 3-4. status
        in_conflict = any(claims_conflict(a, b, text_hash) for a, b in combinations(own, 2))
        if not own:
            status = "uncovered"
        elif in_conflict:
            status = "conflict"
        elif len(positions) > 1:
            status = "complementary"
        else:
            status = "consistent"

        # 6. most-supported position first; counts are shown, nothing is marked as correct
        ordered = sorted(positions.values(), key=lambda p: -len(p["document_ids"]))
        for position in ordered:
            del position["_hashes"]

        result.append(
            {
                "id": aspect.id,
                "label": aspect.label,
                "status": status,
                "basis": "text" if any(_family(k) == "text" for k in positions) else "typed",  # 5
                "positions": ordered,
                "notes": [],
            }
        )

    # 7. verified supersession notes attach to their aspect and never change its status
    for note in notes or []:
        target = next((a for a in result if a["id"] == note.get("aspect_id")), None)
        if target is None and len(result) == 1:
            target = result[0]
        if target is not None:
            target["notes"].append({"text": note["text"], "evidence": note["evidence"]})
    return result


def fallback(aspects: list, claims: list[dict]) -> list[dict]:
    """Used when detect() raises: every covered aspect is reported as consistent, with no positions."""
    return [
        {
            "id": aspect.id,
            "label": aspect.label,
            "status": "consistent" if any(c["aspect_id"] == aspect.id for c in claims) else "uncovered",
            "basis": "typed",
            "positions": [],
            "notes": [],
        }
        for aspect in aspects
    ]
