"""Page-bounded, paragraph-aware chunking with no overlap (LLD section 7.5)."""
import hashlib
import re

TARGET_CHARS = 900
MAX_PARAGRAPH_CHARS = 1200
MIN_CHUNK_CHARS = 40

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WS = re.compile(r"\s+")


def text_hash(text: str) -> str:
    return hashlib.sha256(_WS.sub(" ", text.lower()).strip().encode("utf-8")).hexdigest()


def _split_long(text: str) -> list[str]:
    pieces, current = [], ""
    for sentence in _SENTENCE_END.split(text):
        while len(sentence) > TARGET_CHARS:  # a single very long sentence
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:TARGET_CHARS])
            sentence = sentence[TARGET_CHARS:]
        if current and len(current) + 1 + len(sentence) > TARGET_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_pages(pages: list) -> list[dict]:
    """Return chunk dicts: page, section, paragraph_index, text, extraction_method, ocr_confidence."""
    chunks: list[dict] = []
    section: str | None = None
    paragraph_number = 0

    for page in pages:
        parts: list[str] = []
        first_index = 0
        has_body = False

        def flush():
            nonlocal parts, has_body
            if parts:
                chunks.append(
                    {
                        "page": page.page,
                        "section": section,
                        "paragraph_index": first_index,
                        "text": "\n".join(parts),
                        "extraction_method": page.method,
                        "ocr_confidence": page.ocr_confidence,
                    }
                )
            parts, has_body = [], False

        for para in page.paragraphs:
            paragraph_number += 1
            if para.is_heading:
                flush()
                section = para.text
                parts, first_index = [para.text], paragraph_number
                continue
            if len(para.text) > MAX_PARAGRAPH_CHARS:
                heading = parts if parts and not has_body else []
                if not heading:
                    flush()
                start = first_index if heading else paragraph_number
                parts = []
                for i, piece in enumerate(_split_long(para.text)):
                    parts = (heading if i == 0 else []) + [piece]
                    first_index = start if i == 0 else paragraph_number
                    flush()
                continue
            if has_body and len("\n".join(parts)) + 1 + len(para.text) > TARGET_CHARS:
                flush()
            if not parts:
                first_index = paragraph_number
            parts.append(para.text)
            has_body = True
        flush()

    # merge very small chunks into the previous chunk on the same page, or drop them
    merged: list[dict] = []
    for chunk in chunks:
        if len(chunk["text"]) < MIN_CHUNK_CHARS:
            if merged and merged[-1]["page"] == chunk["page"]:
                merged[-1]["text"] += "\n" + chunk["text"]
            continue
        merged.append(chunk)

    for ordinal, chunk in enumerate(merged):
        chunk["ordinal"] = ordinal
        chunk["text_hash"] = text_hash(chunk["text"])
    return merged
