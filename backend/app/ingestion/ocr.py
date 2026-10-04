"""Local OCR with rapidocr-onnxruntime (LLD section 7.3)."""
import statistics
import threading

from . import IngestionError

OCR_LOW_THRESHOLD = 0.80  # mean confidence below this is "low" quality

_lock = threading.Lock()
_engine = None
_failed = False


def _get_engine():
    global _engine, _failed
    with _lock:
        if _engine is None and not _failed:
            try:
                from rapidocr_onnxruntime import RapidOCR

                _engine = RapidOCR()
            except Exception:
                _failed = True
        if _engine is None:
            raise IngestionError("OCR engine unavailable")
        return _engine


def status() -> str:
    return "unavailable" if _failed else "ok"


def ocr_image(image) -> tuple[list[str], float | None]:
    """OCR a numpy image or an image path. Returns (paragraph texts, mean line confidence)."""
    engine = _get_engine()
    with _lock:
        result, _ = engine(image)
    if not result:
        return [], None

    lines = []
    for box, text, score in result:
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        if str(text).strip():
            lines.append({"top": min(ys), "bottom": max(ys), "left": min(xs), "text": str(text).strip(), "score": float(score)})
    if not lines:
        return [], None

    median_height = statistics.median(l["bottom"] - l["top"] for l in lines) or 1.0

    # group detections into visual rows (top-to-bottom), each row left-to-right
    lines.sort(key=lambda l: (l["top"] + l["bottom"]) / 2)
    rows: list[list[dict]] = []
    for line in lines:
        center = (line["top"] + line["bottom"]) / 2
        if rows:
            last = rows[-1]
            last_center = sum((l["top"] + l["bottom"]) / 2 for l in last) / len(last)
            if center - last_center <= 0.5 * median_height:
                last.append(line)
                continue
        rows.append([line])

    paragraphs: list[list[str]] = []
    previous_bottom = None
    for row in rows:
        row.sort(key=lambda l: l["left"])
        top = min(l["top"] for l in row)
        text = " ".join(l["text"] for l in row)
        if previous_bottom is not None and top - previous_bottom <= 1.5 * median_height:
            paragraphs[-1].append(text)
        else:
            paragraphs.append([text])
        previous_bottom = max(l["bottom"] for l in row)

    confidence = sum(l["score"] for l in lines) / len(lines)
    return ["\n".join(p) for p in paragraphs], confidence
