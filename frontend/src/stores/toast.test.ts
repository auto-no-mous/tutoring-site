import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useToastStore } from "@/stores/toast";

describe("useToastStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("adds a toast on show()", () => {
    const store = useToastStore();
    store.show("Сохранено");
    expect(store.toasts).toHaveLength(1);
    expect(store.toasts[0].message).toBe("Сохранено");
  });

  it("auto-dismisses after the given duration", () => {
    const store = useToastStore();
    store.show("Готово", 1000);
    expect(store.toasts).toHaveLength(1);

    vi.advanceTimersByTime(999);
    expect(store.toasts).toHaveLength(1);

    vi.advanceTimersByTime(1);
    expect(store.toasts).toHaveLength(0);
  });

  it("keeps toasts with distinct ids when shown in quick succession", () => {
    const store = useToastStore();
    store.show("Первое");
    store.show("Второе");
    expect(store.toasts).toHaveLength(2);
    expect(store.toasts[0].id).not.toBe(store.toasts[1].id);
  });
});
