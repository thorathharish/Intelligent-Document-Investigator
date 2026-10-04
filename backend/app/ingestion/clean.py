"""Text cleaning (LLD section 7.4)."""
import re
import unicodedata
from collections import Counter

_PAGE_NUMBER = re.compile(r"^\s*(page\s*)?\d+(\s*(of|/)\s*\d+)?\s*$", re.IGNORECASE)
_WS = re.compile(r"\s+")


def join_lines(lines: list[str]) -> str:
    """Join the lines of one paragraph, repairing words hyphenated across a line break."""
    out = ""
    for line in (l.strip() for l in lines):
        if not line:
            continue
        if out.endswith("-") and len(out) > 1 and out[-2].isalpha() and line[0].islower():
            out = out[:-1] + line
        else:
            out = f"{out} {line}" if out else line
    return out


def clean_text(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def clean_pages(pages: list) -> list:
    """Normalise paragraph text; drop empty paragraphs, page numbers and repeated headers/footers."""
    for page in pages:
        for para in page.paragraphs:
            para.text = clean_text(para.text)
        page.paragraphs = [p for p in page.paragraphs if p.text and not _PAGE_NUMBER.match(p.text)]

    paged = [p for p in pages if p.page is not None and p.paragraphs]
    if len(paged) >= 3:
        for position in (0, -1):
            counts = Counter(p.paragraphs[position].text for p in paged if len(p.paragraphs[position].text) <= 60)
            repeated = {text for text, n in counts.items() if n > len(paged) / 2}
            for page in paged:
                if page.paragraphs and page.paragraphs[position].text in repeated:
                    del page.paragraphs[position]
    return pages
