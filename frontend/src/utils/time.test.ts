import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addDaysIso,
  formatDate,
  formatDateTimeWithMsk,
  formatDayLabel,
  formatLocalHint,
  formatThreadTimestamp,
  formatTime,
  mskOffsetHours,
  todayIso,
  nextMskDateForWeekday,
} from "@/utils/time";

describe("formatDate", () => {
  it("renders as DD.MM.YYYY", () => {
    expect(formatDate("2026-03-05T12:00:00Z")).toBe("05.03.2026");
  });
});

describe("formatTime", () => {
  // Время занятий на сайте всегда московское: пока ученику показывали его местное, а
  // репетитору и письмам - московское, один урок назывался двумя числами, и переносы
  // попадали не в тот час.
  it("всегда показывает московское время, независимо от пояса читателя", () => {
    expect(formatTime("2026-03-05T09:00:00Z")).toBe("12:00");
    expect(formatTime("2026-03-05T21:30:00Z")).toBe("00:30");
  });

  it("дата тоже московская - поздний вечер по МСК не уезжает на сутки", () => {
    expect(formatDate("2026-03-05T21:30:00Z")).toBe("06.03.2026");
  });
});

describe("formatDateTimeWithMsk", () => {
  it("помечает время как московское", () => {
    expect(formatDateTimeWithMsk("2026-03-05T09:00:00Z")).toBe("05.03.2026 12:00 (МСК)");
  });
});

describe("mskOffsetHours", () => {
  it("считает разницу с Москвой", () => {
    expect(mskOffsetHours("Europe/Moscow")).toBe(0);
    expect(mskOffsetHours("Asia/Yekaterinburg")).toBe(2);
    expect(mskOffsetHours("Europe/Kaliningrad")).toBe(-1);
  });

  it("не падает на мусорном значении: поле годами было свободным текстом", () => {
    expect(mskOffsetHours("Chelyabinsk")).toBe(0);
  });
});

describe("formatLocalHint", () => {
  it("подсказывает местное время тому, кто живёт не по Москве", () => {
    expect(formatLocalHint("2026-03-05T09:00:00Z", "Asia/Yekaterinburg")).toBe("у вас 14:00");
  });

  it("москвичу подсказывать нечего", () => {
    expect(formatLocalHint("2026-03-05T09:00:00Z", "Europe/Moscow")).toBe("");
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
