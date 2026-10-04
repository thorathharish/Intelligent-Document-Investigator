"""Extraction: pdf / docx / txt / image -> pages of paragraphs (LLD section 7.2)."""
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import IngestionError, ocr
from .clean import join_lines
from .validate import decode_text

HEADING_RE = re.compile(r"^(\d+(\.\d+)*\.?|Section|Article|Clause|Schedule|Annex)\s+\S")
_COLON_THEN_TEXT = re.compile(r":\s*\S")
MIN_PAGE_TEXT_CHARS = 20
OCR_DPI = 200


@dataclass
class Paragraph:
    text: str
    is_heading: bool = False


@dataclass
class Page:
    page: int | None
    method: str  # "text" | "ocr"
    ocr_confidence: float | None = None
    paragraphs: list[Paragraph] = field(default_factory=list)


def is_heading(text: str, single_line: bool, big: bool = False, bold: bool = False, style: bool = False) -> bool:
    t = text.strip()
    if not single_line or not t or len(t) > 80:
        return False
    if t[-1] in ".,;" or _COLON_THEN_TEXT.search(t):
        return False
    if big or bold or style:
        return True
    if HEADING_RE.match(t):
        return True
    return len(t.split()) >= 2 and t.isupper()


def _ocr_page(image, page_number: int) -> Page:
    texts, confidence = ocr.ocr_image(image)
    paragraphs = []
    for text in texts:
        lines = text.split("\n")
        paragraphs.append(Paragraph(join_lines(lines), is_heading(lines[0], len(lines) == 1)))
    return Page(page=page_number, method="ocr", ocr_confidence=confidence, paragraphs=paragraphs)


def _weighted_median(sizes: Counter) -> float:
    total = sum(sizes.values())
    running = 0
    for size in sorted(sizes):
        running += sizes[size]
        if running * 2 >= total:
            return size
    return 0.0


def extract_pdf(path: Path) -> tuple[list[Page], int]:
    import numpy as np
    import pymupdf

    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise IngestionError("Could not open this PDF") from exc

    with doc:
        raw_pages = []
        sizes: Counter = Counter()
        for page in doc:
            blocks = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                lines, max_size, all_bold = [], 0.0, True
                for line in block.get("lines", []):
                    spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                    if not spans:
                        continue
                    lines.append("".join(s["text"] for s in line["spans"]))
                    for span in spans:
                        sizes[round(span["size"], 1)] += len(span["text"])
                        max_size = max(max_size, span["size"])
                        if not (span.get("flags", 0) & 16 or "bold" in span.get("font", "").lower()):
                            all_bold = False
                if lines:
                    blocks.append((lines, max_size, all_bold))
            raw_pages.append((page, blocks))

        body_size = _weighted_median(sizes)
        pages: list[Page] = []
        for number, (page, blocks) in enumerate(raw_pages, start=1):
            if sum(len(line) for lines, _, _ in blocks for line in lines) < MIN_PAGE_TEXT_CHARS:
                pix = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csRGB, alpha=False)
                image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                pages.append(_ocr_page(image, number))
                continue
            paragraphs = []
            for lines, max_size, all_bold in blocks:
                text = join_lines(lines)
                big = body_size > 0 and max_size >= 1.15 * body_size
                paragraphs.append(Paragraph(text, is_heading(text, len(lines) == 1, big=big, bold=all_bold)))
            pages.append(Page(page=number, method="text", paragraphs=paragraphs))
        return pages, len(raw_pages)


def extract_docx(path: Path) -> tuple[list[Page], None]:
    import docx
    from docx.table import Table

    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise IngestionError("Could not open this Word document") from exc

    paragraphs = []
    for item in document.iter_inner_content():
        if isinstance(item, Table):
            for row in item.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    paragraphs.append(Paragraph(" | ".join(cells)))
            continue
        text = item.text.strip()
        if not text:
            continue
        style = (item.style.name or "") if item.style is not None else ""
        runs = [r for r in item.runs if r.text.strip()]
        bold = bool(runs) and all(r.bold for r in runs)
        heading = is_heading(text, "\n" not in text, bold=bold, style=style.startswith("Heading"))
        paragraphs.append(Paragraph(join_lines(text.split("\n")), heading))
    return [Page(page=None, method="text", paragraphs=paragraphs)], None


def extract_txt(path: Path) -> tuple[list[Page], None]:
    text = decode_text(path.read_bytes()).replace("\r\n", "\n")
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line for line in block.split("\n") if line.strip()]
        if lines:
            paragraphs.append(Paragraph(join_lines(lines), is_heading(lines[0], len(lines) == 1)))
    return [Page(page=None, method="text", paragraphs=paragraphs)], None


def extract_image(path: Path) -> tuple[list[Page], int]:
    return [_ocr_page(str(path), 1)], 1


def extract(path: Path, ext: str) -> tuple[list[Page], int | None]:
    """Return (pages, page_count). page_count is None for formats without pages."""
    if ext == "pdf":
        return extract_pdf(path)
    if ext == "docx":
        return extract_docx(path)
    if ext == "txt":
        return extract_txt(path)
    if ext in ("png", "jpg"):
        return extract_image(path)
    raise IngestionError("Unsupported file type")
