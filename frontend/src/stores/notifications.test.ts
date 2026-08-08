import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUnreadSummary } from "@/api/notifications";
import { useNotificationsStore } from "@/stores/notifications";

vi.mock("@/api/notifications", () => ({
  getUnreadSummary: vi.fn(),
}));

const mockedGetUnreadSummary = vi.mocked(getUnreadSummary);

describe("useNotificationsStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    mockedGetUnreadSummary.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("aggregates chat and system unread counts from the summary endpoint", async () => {
    mockedGetUnreadSummary.mockResolvedValue({ chat_unread: 2, system_unread: 3, total: 5 });
    const store = useNotificationsStore();

    await store.refresh();

    expect(store.chatUnread).toBe(2);
    expect(store.systemUnread).toBe(3);
    expect(store.total).toBe(5);
  });

  it("leaves existing counts untouched if the request fails (e.g. logged out)", async () => {
    mockedGetUnreadSummary.mockResolvedValueOnce({ chat_unread: 1, system_unread: 1, total: 2 });
    const store = useNotificationsStore();
    await store.refresh();
    expect(store.total).toBe(2);

    mockedGetUnreadSummary.mockRejectedValueOnce(new Error("network error"));
    await store.refresh();
    expect(store.total).toBe(2);
  });

  it("polls on an interval while started, and stops (resetting counts) when stopped", async () => {
    mockedGetUnreadSummary.mockResolvedValue({ chat_unread: 1, system_unread: 0, total: 1 });
    const store = useNotificationsStore();

    store.startPolling();
    await vi.waitFor(() => expect(mockedGetUnreadSummary).toHaveBeenCalledTimes(1));
    expect(store.total).toBe(1);

    await vi.advanceTimersByTimeAsync(15000);
    expect(mockedGetUnreadSummary).toHaveBeenCalledTimes(2);

    store.stopPolling();
    expect(store.total).toBe(0);
    expect(store.chatUnread).toBe(0);
    expect(store.systemUnread).toBe(0);

    await vi.advanceTimersByTimeAsync(15000);
    // No further calls once polling has stopped.
    expect(mockedGetUnreadSummary).toHaveBeenCalledTimes(2);
  });
});
