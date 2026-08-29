import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Chat attachments and homework files/submissions accept a broader set of everyday
# document formats, but deliberately exclude anything a browser would execute or
# interpret as markup (html, svg, js, ...) - see security review notes on the /files
# static mount being same-origin with the SPA.
ALLOWED_ATTACHMENT_TYPES = ALLOWED_IMAGE_TYPES | {
    "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "application/zip",
}

# The stored file's extension is derived from this server-side, validated-content-type
# lookup - never from the client-supplied filename - so a spoofed Content-Type header
# paired with e.g. filename="x.html" can't smuggle an executable-in-the-browser
# extension onto disk (the actual bug this closes: previously the extension came
# straight from the untrusted filename regardless of the checked content type).
_CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/plain": ".txt",
    "application/zip": ".zip",
}


async def save_upload(file: UploadFile, subdir: str, allowed_types: set[str]) -> str:
    """Saves an uploaded file under storage/<subdir>/ and returns a URL served via the
    /files static mount (see app/main.py). Local disk for now, S3-compatible storage
    later per project_description.md section 10.

    `allowed_types` is required (not optional) - every call site must declare an
    explicit content-type allow-list, since /files is served same-origin with the SPA
    and an unrestricted upload (e.g. an .html file) would render as a same-origin
    page rather than downloading, enabling stored XSS."""
    contents = await file.read()
    return save_bytes(contents, file.content_type or "", subdir, allowed_types)


def save_bytes(contents: bytes, content_type: str, subdir: str, allowed_types: set[str]) -> str:
    """Та же запись в storage, но для содержимого, которое пришло не файлом от
    браузера: например, аватар, скачанный у VK/Яндекса при регистрации через них
    (см. app.services.oauth_service). Проверки те же - тип из белого списка и
    ограничение размера."""
    if content_type not in allowed_types:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Недопустимый тип файла")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Файл больше {settings.max_upload_size_mb} МБ"
        )

    ext = _CONTENT_TYPE_EXTENSIONS.get(content_type, "")
    filename = f"{uuid.uuid4().hex}{ext}"
    target_dir = settings.storage_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(contents)

    return f"/files/{subdir}/{filename}"
