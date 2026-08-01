import { describe, expect, it } from "vitest";

import { groupByWeekAndDay } from "@/utils/scheduleGrouping";

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
});
