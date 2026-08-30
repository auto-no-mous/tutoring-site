import { afterEach, describe, expect, it, vi } from "vitest";

import { addDaysIso, formatDate, formatDateTimeWithMsk, formatDayLabel, formatThreadTimestamp, todayIso, nextMskDateForWeekday } from "@/utils/time";

describe("formatDate", () => {
  it("renders as DD.MM.YYYY", () => {
    expect(formatDate("2026-03-05T12:00:00Z")).toBe("05.03.2026");
  });
});

describe("formatDateTimeWithMsk", () => {
  it("includes both local and MSK time", () => {
    const result = formatDateTimeWithMsk("2026-03-05T12:00:00Z");
    expect(result).toContain("05.03.2026");
    expect(result).toContain("МСК");
  });
});

describe("addDaysIso", () => {
  it("adds whole days without crossing into fractional/timezone drift", () => {
    expect(addDaysIso("2026-03-05", 1)).toBe("2026-03-06");
    expect(addDaysIso("2026-03-05", 30)).toBe("2026-04-04");
  });

  it("rolls over year boundaries", () => {
    expect(addDaysIso("2026-12-31", 1)).toBe("2027-01-01");
  });
});

describe("todayIso", () => {
  it("returns a YYYY-MM-DD string", () => {
    expect(todayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe("formatDayLabel", () => {
  it("returns 'Сегодня' for today", () => {
    expect(formatDayLabel(new Date().toISOString())).toBe("Сегодня");
  });

  it("returns 'Вчера' for yesterday", () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    expect(formatDayLabel(yesterday.toISOString())).toBe("Вчера");
  });

  it("returns a formatted date for older days", () => {
    expect(formatDayLabel("2020-01-01T12:00:00Z")).toBe(formatDate("2020-01-01T12:00:00Z"));
  });
});

describe("formatThreadTimestamp", () => {
  it("returns just the time for today", () => {
    expect(formatThreadTimestamp(new Date().toISOString())).toMatch(/^\d{2}:\d{2}$/);
  });

  it("returns a short date for older messages", () => {
    expect(formatThreadTimestamp("2020-01-01T12:00:00Z")).toMatch(/^\d{2}\.\d{2}$/);
  });
});

describe("nextMskDateForWeekday", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("выбирает ближайший нужный день недели по МСК", () => {
    // Среда, 1 июля 2026, 10:00 МСК (07:00 UTC).
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-01T07:00:00Z"));

    // Пятница той же недели.
    expect(nextMskDateForWeekday(4, "18:00")).toBe("2026-07-03");
    // Понедельник - уже следующей.
    expect(nextMskDateForWeekday(0, "18:00")).toBe("2026-07-06");
  });

  it("переносит на следующую неделю, если сегодня время уже прошло", () => {
    vi.useFakeTimers();
    // Среда, 19:00 МСК.
    vi.setSystemTime(new Date("2026-07-01T16:00:00Z"));

    // 18:00 сегодня уже позади - первое занятие серии не должно попасть в прошлое.
    expect(nextMskDateForWeekday(2, "18:00")).toBe("2026-07-08");
    // А 20:00 ещё впереди.
    expect(nextMskDateForWeekday(2, "20:00")).toBe("2026-07-01");
  });
});
