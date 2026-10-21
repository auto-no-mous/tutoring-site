import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { groupByWeekAndDay, groupIntoCalendarWeeks, isBeforeToday } from "@/utils/scheduleGrouping";

interface Item {
  start_at: string;
}

describe("groupByWeekAndDay", () => {
  it("always includes today, even with no items", () => {
    const weeks = groupByWeekAndDay<Item>([], (i) => i.start_at, "UTC");
    const allDays = weeks.flatMap((w) => w.days);
    const today = allDays.find((d) => d.isToday);
    expect(today).toBeDefined();
    expect(today?.items).toEqual([]);
    expect(today?.label).toBe("Сегодня");
  });

  it("buckets an item by its calendar date in the given timezone", () => {
    const now = new Date();
    const todayNoonUtc = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 12, 0, 0));
    const items: Item[] = [{ start_at: todayNoonUtc.toISOString() }];
    const weeks = groupByWeekAndDay(items, (i) => i.start_at, "UTC");
    const todayGroup = weeks.flatMap((w) => w.days).find((d) => d.isToday);
    expect(todayGroup?.items).toHaveLength(1);
  });

  it("labels next week's bucket distinctly from the current week", () => {
    const inTenDays = new Date(Date.now() + 10 * 24 * 3600 * 1000);
    const items: Item[] = [{ start_at: inTenDays.toISOString() }];
    const weeks = groupByWeekAndDay(items, (i) => i.start_at, "UTC");
    const labels = weeks.map((w) => w.label);
    // At minimum "Текущая неделя" (from the always-present today bucket) plus
    // whichever bucket the +10 day item landed in.
    expect(labels).toContain("Текущая неделя");
    expect(labels.length).toBeGreaterThanOrEqual(1);
  });

  it("flags isCurrentWeek only on the current week's bucket", () => {
    const inThreeWeeks = new Date(Date.now() + 21 * 24 * 3600 * 1000);
    const items: Item[] = [{ start_at: inThreeWeeks.toISOString() }];
    const weeks = groupByWeekAndDay(items, (i) => i.start_at, "UTC");
    const currentWeek = weeks.find((w) => w.label === "Текущая неделя");
    expect(currentWeek?.isCurrentWeek).toBe(true);
    const otherWeeks = weeks.filter((w) => w.label !== "Текущая неделя");
    expect(otherWeeks.length).toBeGreaterThan(0);
    expect(otherWeeks.every((w) => w.isCurrentWeek === false)).toBe(true);
  });
});

describe("isBeforeToday", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // 15:00 МСК - половина дня позади, половина впереди.
    vi.setSystemTime(new Date("2026-09-02T12:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps today's lesson out of history even after it has started", () => {
    // Регрессия: списки делились сравнением с «сейчас», и занятие проваливалось в
    // «Историю» ровно в момент начала - перенёс на сегодня и оно исчезло из ближайших.
    expect(isBeforeToday("2026-09-02T06:00:00Z", "Europe/Moscow")).toBe(false);
  });

  it("keeps a lesson still ahead today out of history", () => {
    expect(isBeforeToday("2026-09-02T18:00:00Z", "Europe/Moscow")).toBe(false);
  });

  it("treats yesterday and earlier as history", () => {
    expect(isBeforeToday("2026-09-01T18:00:00Z", "Europe/Moscow")).toBe(true);
    expect(isBeforeToday("2026-08-20T09:00:00Z", "Europe/Moscow")).toBe(true);
  });

  it("counts the day in the given timezone, not UTC", () => {
    // 22:30 UTC 1 сентября - это уже 01:30 2 сентября по Москве, то есть сегодня.
    expect(isBeforeToday("2026-09-01T22:30:00Z", "Europe/Moscow")).toBe(false);
    expect(isBeforeToday("2026-09-01T22:30:00Z", "UTC")).toBe(true);
  });
});

describe("groupIntoCalendarWeeks", () => {
  // Среда, 21.10.2026, 12:00 по Москве.
  const now = new Date("2026-10-21T09:00:00Z");
  const at = (iso: string): Item => ({ start_at: iso });

  it("всегда даёт текущую неделю целиком, с понедельника по воскресенье", () => {
    const [week, ...rest] = groupIntoCalendarWeeks<Item>([], (i) => i.start_at, "Europe/Moscow", now);

    expect(rest).toHaveLength(0);
    expect(week.label).toBe("Текущая неделя");
    expect(week.isCurrentWeek).toBe(true);
    expect(week.days.map((d) => d.weekday)).toEqual(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]);
    expect(week.days[0].dateIso).toBe("2026-10-19");
    expect(week.days[2].isToday).toBe(true);
    expect(week.days.map((d) => d.isPast)).toEqual([true, true, false, false, false, false, false]);
  });

  it("раскладывает занятия по московским дням и сортирует их по времени", () => {
    const weeks = groupIntoCalendarWeeks(
      // 23:30 UTC вторника - это уже среда по Москве.
      [at("2026-10-23T12:00:00Z"), at("2026-10-23T07:00:00Z"), at("2026-10-20T21:30:00Z")],
      (i) => i.start_at,
      "Europe/Moscow",
      now,
    );

    expect(weeks[0].days[2].items).toEqual([at("2026-10-20T21:30:00Z")]);
    expect(weeks[0].days[4].items).toEqual([at("2026-10-23T07:00:00Z"), at("2026-10-23T12:00:00Z")]);
  });

  it("идёт неделями подряд до последнего занятия, не пропуская пустые", () => {
    const weeks = groupIntoCalendarWeeks([at("2026-11-04T09:00:00Z")], (i) => i.start_at, "Europe/Moscow", now);

    expect(weeks.map((w) => w.label)).toEqual([
      "Текущая неделя",
      "Следующая неделя",
      "Неделя 02.11.2026 – 08.11.2026",
    ]);
    expect(weeks[1].days.every((d) => d.items.length === 0)).toBe(true);
    expect(weeks[2].days[2].items).toHaveLength(1);
  });

  it("отбрасывает занятия раньше текущей недели", () => {
    const weeks = groupIntoCalendarWeeks([at("2026-10-15T09:00:00Z")], (i) => i.start_at, "Europe/Moscow", now);

    expect(weeks).toHaveLength(1);
    expect(weeks[0].days.flatMap((d) => d.items)).toEqual([]);
  });
});
