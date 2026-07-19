// Section 6: the student always sees their own local time, with the MSK-equivalent
// shown alongside, e.g. "18:00 (МСК 15:00)".

export function formatTime(isoUtc: string): string {
  return new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(new Date(isoUtc));
}

export function formatMskTime(isoUtc: string): string {
  return new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow" }).format(
    new Date(isoUtc),
  );
}

export function formatDate(isoUtc: string): string {
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(
    new Date(isoUtc),
  );
}

export function formatDateTimeWithMsk(isoUtc: string): string {
  return `${formatDate(isoUtc)} ${formatTime(isoUtc)} (МСК ${formatMskTime(isoUtc)})`;
}

export function formatTimeWithMsk(isoUtc: string): string {
  return `${formatTime(isoUtc)} (МСК ${formatMskTime(isoUtc)})`;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function addDaysIso(dateIso: string, days: number): string {
  const d = new Date(dateIso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
