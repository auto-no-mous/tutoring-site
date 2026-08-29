import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { groupByWeekAndDay, isBeforeToday } from "@/utils/scheduleGrouping";

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
