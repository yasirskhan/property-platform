# ============================================================
# routers/uploads.py
# ------------------------------------------------------------
# File upload/download endpoints.
#
#   POST /uploads                 upload a file
#   GET  /uploads/{filename}      download/serve a file
#
# Files are stored in backend/uploads/.
# Filenames are auto-generated (UUID + extension) to avoid
# collisions and path traversal.
#
# Future: swap local storage for S3/Cloudflare R2 by replacing
# the save/read functions — the API stays the same.
# ============================================================

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.models.user import User
from app.routers.auth import get_current_user


router = APIRouter(prefix="/uploads", tags=["Uploads"])


# ------------------------------------------------------------
# Allowed file types (extensions) and size limit
# ------------------------------------------------------------
ALLOWED_EXTENSIONS = {
    # Images
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    # Documents
    ".pdf", ".doc", ".docx",
    # Optional: spreadsheets
    ".xls", ".xlsx", ".csv",
}


def _upload_dir() -> Path:
    """Return the upload directory, creating it if needed."""
    # Resolve relative to the backend folder
    base = Path(__file__).resolve().parents[2]  # .../backend
    path = base / settings.UPLOAD_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{ext}' is not allowed",
        )
    return ext


# ------------------------------------------------------------
# UPLOAD
# ------------------------------------------------------------
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a file. Returns { url, filename, size, content_type }.

    Any logged-in user can upload. Authorization for what the
    file is *used for* is enforced elsewhere (e.g. attaching
    a lease PDF requires lease access).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    ext = _safe_extension(file.filename)

    # Read contents to check size
    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum is {settings.MAX_UPLOAD_MB} MB",
        )

    # Generate a unique name
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = _upload_dir() / unique_name

    with open(dest, "wb") as f:
        f.write(contents)

    return {
        "url": f"/uploads/{unique_name}",
        "filename": unique_name,
        "original_name": file.filename,
        "size": len(contents),
        "content_type": file.content_type or "application/octet-stream",
    }


# ------------------------------------------------------------
# SERVE
# ------------------------------------------------------------
@router.get("/{filename}")
def get_file(filename: str):
    """
    Serve an uploaded file.

    Filenames are UUID-based, so they aren't guessable.
    We still validate to prevent path traversal.
    """
    # Reject anything that isn't a plain filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = _upload_dir() / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path)