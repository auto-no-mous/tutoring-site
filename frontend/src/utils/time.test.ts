import { describe, expect, it } from "vitest";

import { addDaysIso, formatDate, formatDateTimeWithMsk, todayIso } from "@/utils/time";

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
