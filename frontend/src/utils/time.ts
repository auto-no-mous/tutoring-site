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

// Russia has used a fixed UTC+3 offset since 2014 (no DST), so a literal offset is
// enough - powers manual date/time entry in the tutor's own manual-booking form
// (components/tutor/BookingsTab.vue), keeping it consistent with the MSK convention
// used everywhere else in the tutor cabinet.
export function mskDateTimeToUtcIso(dateIso: string, timeHm: string): string {
  return new Date(`${dateIso}T${timeHm}:00+03:00`).toISOString();
}

function isSameLocalDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

// Date separator between groups of chat messages (components/ChatPanel.vue) - local
// calendar day, since that's what a "day" intuitively means to whoever's reading it.
export function formatDayLabel(isoUtc: string): string {
  const date = new Date(isoUtc);
  const now = new Date();
  if (isSameLocalDay(date, now)) return "Сегодня";
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (isSameLocalDay(date, yesterday)) return "Вчера";
  return formatDate(isoUtc);
}

// Compact timestamp for the chat thread list (components/ChatPanel.vue): just the
// time for today's messages, otherwise a short date - mirrors common chat apps.
export function formatThreadTimestamp(isoUtc: string): string {
  const date = new Date(isoUtc);
  if (isSameLocalDay(date, new Date())) return formatTime(isoUtc);
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" }).format(date);
}

// Дата статьи в блоге: длинная форма читается лучше, чем 23.08.2026, и у публикации
// нет привязки ко времени занятия, поэтому без часов и МСК.
export function formatArticleDate(isoUtc: string): string {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(
    new Date(isoUtc),
  );
}

/**
 * Ближайшая дата (YYYY-MM-DD) указанного дня недели по московскому времени.
 *
 * Нужна там, где репетитор назначает еженедельное занятие днём недели и временем
 * (components/tutor/StudentsBlock.vue), а серия на бэкенде отсчитывается от даты
 * первого занятия. Сегодняшний день годится, только если это время ещё не прошло:
 * иначе первое занятие серии оказалось бы в прошлом.
 *
 * weekday: 0 = понедельник ... 6 = воскресенье, как в бэкендовых WeeklyAvailability
 * и RecurringSeries.
 */
export function nextMskDateForWeekday(weekday: number, timeHm: string): string {
  // Сдвигаем метку времени так, чтобы локальные поля Date показывали московские
  // часы: считать день недели и час нужно именно по МСК - в нём живёт расписание.
  const mskNow = new Date(Date.now() + new Date().getTimezoneOffset() * 60000 + 3 * 3600000);
  const target = new Date(mskNow);
  const mskWeekday = (mskNow.getDay() + 6) % 7;
  const shift = (weekday - mskWeekday + 7) % 7;
  target.setDate(target.getDate() + shift);

  const [hours, minutes] = timeHm.split(":").map(Number);
  const alreadyPassedToday =
    shift === 0 &&
    (mskNow.getHours() > hours || (mskNow.getHours() === hours && mskNow.getMinutes() >= minutes));
  if (alreadyPassedToday) target.setDate(target.getDate() + 7);

  const pad = (n: number) => String(n).padStart(2, "0");
  return `${target.getFullYear()}-${pad(target.getMonth() + 1)}-${pad(target.getDate())}`;
}
