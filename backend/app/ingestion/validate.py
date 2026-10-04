"""Upload validation (LLD section 7.1). A failure rejects that file only."""
import hashlib

from ..config import settings

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "png", "jpg", "jpeg"}


class ValidationError(Exception):
    """The message is the rejection reason shown to the user."""


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _signature_ok(ext: str, data: bytes) -> bool:
    if ext == "pdf":
        return data.startswith(b"%PDF")
    if ext == "docx":
        return data.startswith(b"PK\x03\x04")
    if ext == "png":
        return data.startswith(b"\x89PNG")
    if ext == "jpg":
        return data.startswith(b"\xff\xd8\xff")
    if ext == "txt":
        if b"\x00" in data:
            return False
        try:
            decode_text(data)
        except UnicodeDecodeError:
            return False
        return True
    return False


def validate_file(filename: str, data: bytes, max_bytes: int | None = None) -> tuple[str, str]:
    """Return (ext, sha256) or raise ValidationError."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Unsupported file type")
    if ext == "jpeg":
        ext = "jpg"
    limit = settings.max_file_mb * 1024 * 1024 if max_bytes is None else max_bytes
    if len(data) == 0:
        raise ValidationError("File is empty")
    if len(data) > limit:
        raise ValidationError(f"File is larger than {settings.max_file_mb} MB")
    if not _signature_ok(ext, data):
        raise ValidationError("File content does not match its extension")
    return ext, hashlib.sha256(data).hexdigest()
