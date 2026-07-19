import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def save_upload(file: UploadFile, subdir: str, allowed_types: set[str] | None = None) -> str:
    """Saves an uploaded file under storage/<subdir>/ and returns a URL served via the
    /files static mount (see app/main.py). Local disk for now, S3-compatible storage
    later per project_description.md section 10."""
    if allowed_types is not None and file.content_type not in allowed_types:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Недопустимый тип файла")

    contents = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Файл больше {settings.max_upload_size_mb} МБ"
        )

    ext = Path(file.filename or "").suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    target_dir = settings.storage_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(contents)

    return f"/files/{subdir}/{filename}"
