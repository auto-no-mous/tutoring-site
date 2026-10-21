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

export function dateInTimeZone(date: Date, timeZone: string): string {
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

// «Текущая неделя» / «Следующая неделя» / «Неделя DD.MM.YYYY – DD.MM.YYYY».
function weekLabel(dateIso: string, todayIso: string): string {
  const d = parseDateOnly(dateIso);
  const currentMonday = mondayOf(parseDateOnly(todayIso));
  const nextMonday = addDays(currentMonday, 7);
  if (d >= currentMonday && d < nextMonday) return "Текущая неделя";
  if (d >= nextMonday && d < addDays(currentMonday, 14)) return "Следующая неделя";
  const mon = mondayOf(d);
  return `Неделя ${formatRuDate(mon)} – ${formatRuDate(addDays(mon, 6))}`;
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

  const weekLabelFor = (dateIso: string) => weekLabel(dateIso, todayIso);

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

/**
 * Занятие относится к прошедшим дням - то есть ко вчера или раньше по календарю в
 * указанном поясе.
 *
 * Именно по календарю, а не по моменту времени. Раньше списки делились сравнением
 * start_at с «сейчас», и занятие проваливалось в «Историю» сразу, как только
 * начиналось: перенёс на сегодня - и оно исчезло из ближайших, хотя день ещё идёт.
 * Сегодняшние занятия должны оставаться наверху списка до конца дня.
 *
 * Даты в формате YYYY-MM-DD сравниваются лексикографически, поэтому строк достаточно.
 */
export function isBeforeToday(startAtIso: string, timeZone: string): boolean {
  return dateInTimeZone(new Date(startAtIso), timeZone) < dateInTimeZone(new Date(), timeZone);
}

const WEEKDAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export interface CalendarDay<T> {
  dateIso: string;
  weekday: string;
  dateLabel: string;
  items: T[];
  isToday: boolean;
  isPast: boolean;
}

export interface CalendarWeek<T> {
  label: string;
  isCurrentWeek: boolean;
  days: CalendarDay<T>[];
}

/**
 * Недельная сетка: недели целиком, с понедельника по воскресенье, все семь дней - даже
 * пустые. В отличие от groupByWeekAndDay, где показываются только дни с занятиями,
 * здесь это календарь, и пропуск дня или недели сбивал бы с толку. Недели идут подряд
 * от текущей до последней, где есть занятия; более ранние элементы отбрасываются.
 */
export function groupIntoCalendarWeeks<T>(
  items: T[],
  getStartAtIso: (item: T) => string,
  timeZone: string,
  now: Date = new Date(),
): CalendarWeek<T>[] {
  const todayIso = dateInTimeZone(now, timeZone);
  const firstMonday = mondayOf(parseDateOnly(todayIso));

  const byDate = new Map<string, T[]>();
  let lastDateIso = todayIso;
  for (const item of items) {
    const dateIso = dateInTimeZone(new Date(getStartAtIso(item)), timeZone);
    if (parseDateOnly(dateIso) < firstMonday) continue;
    if (!byDate.has(dateIso)) byDate.set(dateIso, []);
    byDate.get(dateIso)!.push(item);
    if (dateIso > lastDateIso) lastDateIso = dateIso;
  }
  for (const list of byDate.values()) {
    list.sort((a, b) => getStartAtIso(a).localeCompare(getStartAtIso(b)));
  }

  const lastMonday = mondayOf(parseDateOnly(lastDateIso));
  const weeks: CalendarWeek<T>[] = [];
  for (let monday = firstMonday; monday <= lastMonday; monday = addDays(monday, 7)) {
    const mondayIso = toDateOnlyIso(monday);
    weeks.push({
      label: weekLabel(mondayIso, todayIso),
      isCurrentWeek: monday.getTime() === firstMonday.getTime(),
      days: WEEKDAY_SHORT.map((weekday, i) => {
        const dateIso = toDateOnlyIso(addDays(monday, i));
        return {
          dateIso,
          weekday,
          dateLabel: formatRuDateShort(addDays(monday, i)),
          items: byDate.get(dateIso) ?? [],
          isToday: dateIso === todayIso,
          isPast: dateIso < todayIso,
        };
      }),
    });
  }
  return weeks;
}
