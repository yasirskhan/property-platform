"""Local storage adapter for universal entity attachments."""
from __future__ import annotations

from pathlib import Path
import uuid

from app.core.config import settings


ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv",
}


def attachment_root() -> Path:
    base = Path(settings.UPLOAD_DIR)
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[2] / base
    root = base / "entity_attachments"
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_attachment_name(filename: str) -> tuple[str, str]:
    name = Path(filename or "").name.strip()
    if not name:
        raise ValueError("Missing filename")
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValueError(f"File type '{ext}' is not allowed")
    return name[:255], ext


def store_attachment_bytes(*, filename: str, contents: bytes) -> tuple[str, str]:
    original_name, ext = normalize_attachment_name(filename)
    storage_key = f"{uuid.uuid4().hex}{ext}"
    (attachment_root() / storage_key).write_bytes(contents)
    return storage_key, original_name


def attachment_path(storage_key: str) -> Path:
    if not storage_key or "/" in storage_key or "\\" in storage_key or ".." in storage_key:
        raise ValueError("Invalid attachment storage key")
    return attachment_root() / storage_key


def remove_attachment_bytes(storage_key: str) -> None:
    try:
        path = attachment_path(storage_key)
    except ValueError:
        return
    if path.exists() and path.is_file():
        path.unlink()
