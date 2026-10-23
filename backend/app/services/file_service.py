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
    # Так .zip называет Chrome на Windows - без этого архив от репетитора или ученика
    # на Windows отклонялся как «недопустимый тип».
    "application/x-zip-compressed",
    # Форматы LibreOffice (OpenDocument): тексты, таблицы, презентации, рисунки.
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.oasis.opendocument.graphics",
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
    "application/x-zip-compressed": ".zip",
    "application/vnd.oasis.opendocument.text": ".odt",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
    "application/vnd.oasis.opendocument.presentation": ".odp",
    "application/vnd.oasis.opendocument.graphics": ".odg",
}

# Тип файла браузер берёт у операционной системы, и если та формата не знает (на
# Windows без LibreOffice - .odt, .odp и т.п.), присылает пустой тип или
# application/octet-stream. Тогда - и только тогда - тип определяем по расширению
# имени, но лишь среди разрешённых: обратная таблица к _CONTENT_TYPE_EXTENSIONS, так
# что на диск по-прежнему попадает только расширение из белого списка.
_GENERIC_CONTENT_TYPES = {"", "application/octet-stream"}
_EXTENSION_CONTENT_TYPES: dict[str, str] = {".jpeg": "image/jpeg"}
for _type, _ext in _CONTENT_TYPE_EXTENSIONS.items():
    _EXTENSION_CONTENT_TYPES.setdefault(_ext, _type)


def resolve_content_type(content_type: str | None, filename: str | None, allowed_types: set[str]) -> str:
    """Тип загруженного файла: присланный браузером, а если тот ничего не сказал -
    по расширению имени (только для типов из allowed_types)."""
    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type not in _GENERIC_CONTENT_TYPES or not filename or "." not in filename:
        return content_type
    guessed = _EXTENSION_CONTENT_TYPES.get("." + filename.rsplit(".", 1)[1].lower(), "")
    return guessed if guessed in allowed_types else content_type


async def save_upload(file: UploadFile, subdir: str, allowed_types: set[str]) -> str:
    """Saves an uploaded file under storage/<subdir>/ and returns a URL served via the
    /files static mount (see app/main.py). Local disk for now, S3-compatible storage
    later per project_description.md section 10.

    `allowed_types` is required (not optional) - every call site must declare an
    explicit content-type allow-list, since /files is served same-origin with the SPA
    and an unrestricted upload (e.g. an .html file) would render as a same-origin
    page rather than downloading, enabling stored XSS."""
    contents = await file.read()
    content_type = resolve_content_type(file.content_type, file.filename, allowed_types)
    return save_bytes(contents, content_type, subdir, allowed_types)


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
