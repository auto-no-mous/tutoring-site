// Groups a list of dated items into week buckets ("Текущая неделя" / "Следующая
// неделя" / "Неделя DD.MM.YYYY – DD.MM.YYYY"), each containing day buckets
// ("Сегодня" / "Завтра" / weekday name). "Today" is always present, even empty,
// per the UX requirement to show "Сегодня занятий нет".
//
// All date-only arithmetic below uses Date.UTC(...) purely as an integer day
// counter - it never represents a real moment in time, so it can't drift across
// DST. The only place we touch a real timezone is when mapping an item's instant
// (start_at, a UTC ISO string) down to a calendar date via Intl.DateTimeFormat.

const WEEKDAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

export interface DayGroup<T> {
  dateIso: string;
  label: string;
  dateLabel: string;
  items: T[];
  isToday: boolean;
}

export interface WeekGroup<T> {
  label: string;
  isCurrentWeek: boolean;
  days: DayGroup<T>[];
}

function parseDateOnly(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function addDays(d: Date, days: number): Date {
  const copy = new Date(d);
  copy.setUTCDate(copy.getUTCDate() + days);
  return copy;
}

function toDateOnlyIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function mondayOf(d: Date): Date {
  const dow = d.getUTCDay(); // 0=Sunday..6=Saturday
  const diff = dow === 0 ? -6 : 1 - dow;
  return addDays(d, diff);
}

function formatRuDate(d: Date): string {
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}.${d.getUTCFullYear()}`;
}

function formatRuDateShort(d: Date): string {
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}`;
}

function dateInTimeZone(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const y = parts.find((p) => p.type === "year")!.value;
  const m = parts.find((p) => p.type === "month")!.value;
  const d = parts.find((p) => p.type === "day")!.value;
  return `${y}-${m}-${d}`;
}

export function groupByWeekAndDay<T>(
  items: T[],
  getStartAtIso: (item: T) => string,
  timeZone: string,
): WeekGroup<T>[] {
  const todayIso = dateInTimeZone(new Date(), timeZone);
  const byDate = new Map<string, T[]>();
  byDate.set(todayIso, []);
  for (const item of items) {
    const dateIso = dateInTimeZone(new Date(getStartAtIso(item)), timeZone);
    if (!byDate.has(dateIso)) byDate.set(dateIso, []);
    byDate.get(dateIso)!.push(item);
  }
  const sortedDates = [...byDate.keys()].sort();

  const todayDate = parseDateOnly(todayIso);
  const tomorrowIso = toDateOnlyIso(addDays(todayDate, 1));
  const currentMonday = mondayOf(todayDate);
  const nextMonday = addDays(currentMonday, 7);
  const nextNextMonday = addDays(currentMonday, 14);

  function weekLabelFor(dateIso: string): string {
    const d = parseDateOnly(dateIso);
    if (d >= currentMonday && d < nextMonday) return "Текущая неделя";
    if (d >= nextMonday && d < nextNextMonday) return "Следующая неделя";
    const mon = mondayOf(d);
    const sun = addDays(mon, 6);
    return `Неделя ${formatRuDate(mon)} – ${formatRuDate(sun)}`;
  }

  function dayLabelFor(dateIso: string): string {
    if (dateIso === todayIso) return "Сегодня";
    if (dateIso === tomorrowIso) return "Завтра";
    const d = parseDateOnly(dateIso);
    return WEEKDAY_NAMES[(d.getUTCDay() + 6) % 7];
  }

  const weeks: WeekGroup<T>[] = [];
  let currentWeekLabel: string | null = null;
  let currentWeekDays: DayGroup<T>[] = [];

  const CURRENT_WEEK_LABEL = "Текущая неделя";

  for (const dateIso of sortedDates) {
    const label = weekLabelFor(dateIso);
    if (label !== currentWeekLabel) {
      if (currentWeekLabel !== null) {
        weeks.push({ label: currentWeekLabel, isCurrentWeek: currentWeekLabel === CURRENT_WEEK_LABEL, days: currentWeekDays });
      }
      currentWeekLabel = label;
      currentWeekDays = [];
    }
    currentWeekDays.push({
      dateIso,
      label: dayLabelFor(dateIso),
      dateLabel: formatRuDateShort(parseDateOnly(dateIso)),
      items: byDate.get(dateIso)!,
      isToday: dateIso === todayIso,
    });
  }
  if (currentWeekLabel !== null) {
    weeks.push({ label: currentWeekLabel, isCurrentWeek: currentWeekLabel === CURRENT_WEEK_LABEL, days: currentWeekDays });
  }

  return weeks;
}
