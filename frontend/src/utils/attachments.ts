// Какие файлы принимает сервер (backend app/services/file_service.py,
// ALLOWED_ATTACHMENT_TYPES и max_upload_size_mb) - здесь та же договорённость, чтобы
// неподходящий файл отсеивался сразу, понятной фразой, а не после отправки.
//
// Проверка по расширению, а не по типу: тип файла браузер берёт у операционной
// системы, и на Windows он бывает другим или пустым (тот же .zip - это
// application/x-zip-compressed). Окончательное слово всё равно за сервером.

export const ATTACHMENT_EXTENSIONS = [
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".zip",
  ".jpg", ".jpeg", ".png", ".webp", ".gif",
];

/** Для атрибута accept: системный диалог сразу показывает только подходящие файлы. */
export const ATTACHMENT_ACCEPT = ATTACHMENT_EXTENSIONS.join(",");

export const MAX_UPLOAD_MB = 20;

/** Причина, по которой файл не подойдёт, или null. */
export function attachmentProblem(file: File): string | null {
  const dot = file.name.lastIndexOf(".");
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  // Скриншот из буфера обмена приходит без привычного имени, но с типом картинки.
  const isPastedImage = !ext && file.type.startsWith("image/");
  if (!isPastedImage && !ATTACHMENT_EXTENSIONS.includes(ext)) {
    return `Такой файл не подойдёт${ext ? ` (${ext})` : ""}. Можно: PDF, Word, Excel, PowerPoint, TXT, ZIP или картинку.`;
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `Файл больше ${MAX_UPLOAD_MB} МБ - уменьшите его или положите в облако и дайте ссылку.`;
  }
  return null;
}
