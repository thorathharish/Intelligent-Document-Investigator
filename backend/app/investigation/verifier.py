"""Evidence verification (LLD section 11). Nothing the model says is shown unless it passes here."""
import re
import unicodedata

from rapidfuzz import fuzz

from ..ingestion.ocr import OCR_LOW_THRESHOLD
from ..schemas import AnalystOutput
from .normalize import normalize_scope, normalize_value, quote_supports

MIN_QUOTE_CHARS = 10
MAX_QUOTE_CHARS = 300
MIN_SEGMENT_CHARS = 12
FUZZY_TEXT = 92
FUZZY_OCR = 88
TYPED = {"duration", "date", "money", "percent", "number", "boolean"}

_CHAR_MAP = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "‑": "-", "−": "-"}
_ELLIPSIS = re.compile(r"\.{3,}|…")
_EDGE = " \t\n\"'.…"


def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Lower-cased, NFKC, ASCII quotes/dashes, single spaces. Also maps each output char to its source index."""
    out: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", _CHAR_MAP.get(ch, ch)):
            c = _CHAR_MAP.get(c, c).lower()
            if c.isspace():
                if out and out[-1] == " ":
                    continue
                c = " "
            out.append(c)
            index.append(i)
    return "".join(out), index


def _normalise_quote(quote: str) -> str:
    # ellipses are kept here so the segment rule can see them
    text, _ = _normalise_with_map(quote.strip().strip("\"'“”‘’ \t\n"))
    return text.strip()


def find_quote(quote: str, chunk_text: str, is_ocr: bool) -> tuple[int, int] | None:
    """Return the (start, end) span of the quote inside chunk_text, or None."""
    needle = _normalise_quote(quote)
    haystack, index = _normalise_with_map(chunk_text)
    if not needle or not haystack:
        return None

    def span(start: int, end: int) -> tuple[int, int]:
        return index[start], index[end - 1] + 1

    plain = needle.strip(_EDGE)
    if plain and not _ELLIPSIS.search(plain):
        at = haystack.find(plain)
        if at != -1:
            return span(at, at + len(plain))

    if _ELLIPSIS.search(needle):
        segments = [s.strip() for s in _ELLIPSIS.split(needle) if len(s.strip()) >= MIN_SEGMENT_CHARS]
        cursor, first, last = 0, None, None
        for segment in segments:
            at = haystack.find(segment, cursor)
            if at == -1:
                first = None
                break
            first = at if first is None else first
            cursor = last = at + len(segment)
        if segments and first is not None:
            return span(first, last)

    alignment = fuzz.partial_ratio_alignment(plain, haystack)
    if alignment and alignment.score >= (FUZZY_OCR if is_ocr else FUZZY_TEXT) and alignment.dest_end > alignment.dest_start:
        return span(alignment.dest_start, alignment.dest_end)
    return None


def _ocr_quality(item: dict) -> str | None:
    if item["extraction_method"] != "ocr":
        return None
    confidence = item.get("ocr_confidence")
    return "low" if confidence is not None and confidence < OCR_LOW_THRESHOLD else "good"


def verify(output: AnalystOutput, evidence: list[dict]) -> dict:
    """Returns {"claims": [verified claim dicts], "dropped": [{"id", "reason"}]}.

    Location fields come from the evidence items (database rows), never from the model.
    """
    by_eid = {item["eid"]: item for item in evidence}
    aspect_ids = {a.id for a in output.aspects}
    verified: list[dict] = []
    dropped: list[dict] = []
    seen: set[tuple] = set()

    for claim in output.claims:
        item = by_eid.get(claim.evidence)
        if item is None:
            dropped.append({"id": claim.id, "reason": "unknown_evidence"})
            continue
        if claim.aspect not in aspect_ids:
            dropped.append({"id": claim.id, "reason": "unknown_aspect"})
            continue
        quote = claim.quote.strip()
        if not MIN_QUOTE_CHARS <= len(quote) <= MAX_QUOTE_CHARS:
            dropped.append({"id": claim.id, "reason": "bad_quote_length"})
            continue
        found = find_quote(quote, item["text"], item["extraction_method"] == "ocr")
        if found is None:
            dropped.append({"id": claim.id, "reason": "quote_not_found"})
            continue
        shown_quote = item["text"][found[0] : found[1]]  # always the stored document text

        explicit = claim.explicit
        normalized = normalize_value(claim.value, claim.value_type)
        position_key = normalized.key if normalized else None
        if normalized and claim.value_type in TYPED and normalized.family != "text":
            if not quote_supports(normalized, shown_quote):
                # the quote is real but does not state this value: keep as inferred, never comparable
                explicit, position_key = False, None

        dedupe_key = (claim.aspect, item["chunk_id"], position_key or shown_quote.lower())
        if dedupe_key in seen:
            dropped.append({"id": claim.id, "reason": "duplicate"})
            continue
        seen.add(dedupe_key)

        verified.append(
            {
                "id": claim.id,
                "aspect_id": claim.aspect,
                "value": normalized.display if normalized and position_key else claim.value,
                "value_type": claim.value_type,
                "position_key": position_key,
                "scope": normalize_scope(claim.scope),
                "explicit": explicit,
                "evidence": {
                    "chunk_id": item["chunk_id"],
                    "document_id": item["document_id"],
                    "document": item["document"],
                    "page": item["page"],
                    "section": item["section"],
                    "paragraph": item["paragraph"],
                    "quote": shown_quote,
                    "extraction_method": item["extraction_method"],
                    "ocr_quality": _ocr_quality(item),
                },
            }
        )
    return {"claims": verified, "dropped": dropped}
