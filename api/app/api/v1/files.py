import io
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from loguru import logger
from PIL import Image

from app.core.config import settings
from app.core.deps import RateLimit
from app.core.error_codes import E
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import get_jwt_user
from app.schemas.file import FileUploadResponse

router = APIRouter(prefix="/files", tags=["files"])

_ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".csv", ".json"}
_ALLOWED_MIME_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "application/pdf",
    "text/csv",
    "application/json",
}
_MAGIC_BYTES: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],
    "application/pdf": [b"%PDF"],
    "image/svg+xml": [b"<svg", b"<?xml", b"<!DOCTYPE"],
}

_ALLOWED_EXTENSIONS_NO_MAGIC: set[str] = {".csv", ".json"}


def _sanitize_file_name(name: str) -> str:
    if ".." in name or name.startswith("/") or "\\" in name or any(ord(c) < 32 for c in name) or len(name) > 500:
        raise ValidationError("Invalid file name", translation_key=E.INVALID_FILE_NAME)
    safe = Path(name).name
    if ".." in safe or safe.startswith("/"):
        raise ValidationError("Invalid file name", translation_key=E.INVALID_FILE_NAME)
    return safe


def _check_magic_bytes(data: bytes) -> bool:
    first_bytes = data[:16]
    if _validate_webp(first_bytes):
        return True
    return any(any(first_bytes[: len(sig)] == sig for sig in signatures) for signatures in _MAGIC_BYTES.values())


def _validate_file(data: bytes, filename: str | None, content_type: str | None) -> None:
    if len(data) > settings.max_upload_size:
        raise ValidationError(
            f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)} MiB",
            translation_key=E.FILE_TOO_LARGE,
        )
    ext = Path(filename or "").suffix.lower() if filename else ""
    if ext and ext not in _ALLOWED_EXTENSIONS:
        raise ValidationError(f"File extension '{ext}' is not allowed", translation_key=E.FILE_EXTENSION_NOT_ALLOWED)
    if content_type and content_type not in _ALLOWED_MIME_TYPES:
        raise ValidationError(f"Content type '{content_type}' is not allowed", translation_key=E.FILE_CONTENT_TYPE_NOT_ALLOWED)
    if ext in _ALLOWED_EXTENSIONS_NO_MAGIC:
        return
    if not _check_magic_bytes(data):
        raise ValidationError("File content does not match expected format", translation_key=E.FILE_CONTENT_MISMATCH)


def _validate_webp(data: bytes) -> bool:
    if len(data) < 12:
        return False
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


_IMAGE_TYPES: set[str] = {"image/jpeg", "image/png", "image/webp"}

_STORAGE_ATTRS = ("temp_storage", "storage", "profile_storage", "store_storage")


async def _locate_file(request: Request, file_name: str) -> tuple[Any, dict[str, Any]] | None:
    """Find which storage bucket holds `file_name` and return (storage, stat).

    Uploads land in temp/profile/store buckets while product images live in the
    main bucket, so lookups must check the same bucket the file was written to.
    """
    for attr in _STORAGE_ATTRS:
        storage = getattr(request.app.state, attr, None)
        if storage is None:
            continue
        stat = await storage.stat_file(file_name)
        if stat is not None:
            return storage, stat
    return None


def _resize_image(data: bytes, content_type: str | None, max_size: int | None = None) -> bytes:
    if max_size is None or content_type not in _IMAGE_TYPES:
        return data
    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        logger.exception("_resize_image: failed to open image")
        return data
    if img.width <= max_size and img.height <= max_size:
        return data
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    fmt = content_type.split("/")[1].upper()
    if fmt == "JPEG":
        fmt = "JPEG"
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=90, optimize=True)
    return buf.getvalue()


async def _handle_upload(
    request: Request,
    file: UploadFile,
    storage_attr: str,
    prefix: str,
    user: str,
    max_size: int | None = None,
) -> FileUploadResponse:
    storage = getattr(request.app.state, storage_attr, None)
    if storage is None:
        raise NotFoundError("Storage not available", translation_key=E.STORAGE_NOT_AVAILABLE)
    data = await file.read()
    _validate_file(data, file.filename, file.content_type)
    data = _resize_image(data, file.content_type, max_size)
    ext = Path(file.filename or "file").suffix if file.filename else ""
    file_name = f"{prefix}{uuid.uuid4()}{ext}" if prefix else f"{uuid.uuid4()}{ext}"
    result_name = await storage.upload_file(
        file_name=file_name,
        data=data,
        content_type=file.content_type or "application/octet-stream",
        metadata={"original_name": _sanitize_file_name(file.filename or file_name), "uploaded_by": user},
    )
    url = storage.get_public_url(result_name)
    return FileUploadResponse(
        file_name=result_name,
        original_name=file.filename or file_name,
        content_type=file.content_type or "application/octet-stream",
        size=len(data),
        url=url,
    )


@router.post("/upload", response_model=FileUploadResponse, status_code=201, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def upload_file(
    request: Request,
    file: UploadFile,
    max_size: int | None = None,
    user: str = Depends(get_jwt_user),
) -> FileUploadResponse:
    result = await _handle_upload(request, file, "temp_storage", "", user, max_size)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = result.file_name
        activity["action"] = "UPLOAD"
        activity["resource_type"] = "file"
        activity["message"] = f"user {user} upload file {result.file_name}"
    return result


@router.post("/upload/profile", response_model=FileUploadResponse, status_code=201, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def upload_profile_photo(
    request: Request,
    file: UploadFile,
    max_size: int | None = None,
    user: str = Depends(get_jwt_user),
) -> FileUploadResponse:
    result = await _handle_upload(request, file, "profile_storage", "", user, max_size)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = result.file_name
        activity["action"] = "UPLOAD"
        activity["resource_type"] = "profile_photo"
        activity["message"] = f"user {user} upload profile photo {result.file_name}"
    return result


@router.post("/upload/store", response_model=FileUploadResponse, status_code=201, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def upload_store_photo(
    request: Request,
    file: UploadFile,
    max_size: int | None = None,
    user: str = Depends(get_jwt_user),
) -> FileUploadResponse:
    result = await _handle_upload(request, file, "store_storage", "", user, max_size)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = result.file_name
        activity["action"] = "UPLOAD"
        activity["resource_type"] = "store_photo"
        activity["message"] = f"user {user} upload store photo {result.file_name}"
    return result


@router.get("/{file_name:path}", dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))])
async def get_file(
    request: Request,
    file_name: str,
    user: str = Depends(get_jwt_user),
) -> RedirectResponse:
    safe_name = _sanitize_file_name(file_name)
    located = await _locate_file(request, safe_name)
    if located is None:
        raise NotFoundError(f"File not found: {safe_name}", translation_key=E.FILE_NOT_FOUND)
    storage, _ = located
    return RedirectResponse(url=storage.get_public_url(safe_name))


@router.delete("/{file_name:path}", status_code=204, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def delete_file(
    request: Request,
    file_name: str,
    user: str = Depends(get_jwt_user),
) -> None:
    safe_name = _sanitize_file_name(file_name)
    located = await _locate_file(request, safe_name)
    if located is None:
        raise NotFoundError(f"File not found: {safe_name}", translation_key=E.FILE_NOT_FOUND)
    storage, stat = located
    metadata = stat.get("metadata") or {}
    if metadata.get("uploaded_by") and metadata["uploaded_by"] != user:
        raise NotFoundError(f"File not found: {safe_name}", translation_key=E.FILE_NOT_FOUND)
    await storage.delete_file(safe_name)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = safe_name
        activity["action"] = "DELETE"
        activity["resource_type"] = "file"
        activity["message"] = f"user {user} delete file {safe_name}"
