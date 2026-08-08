import { defineStore } from "pinia";
import { ref } from "vue";

import { getUnreadSummary } from "@/api/notifications";

// Combined chat + system-notification unread count - powers the red badge on the
// header avatar (UserMenu.vue) and next to "Чат" in the cabinet nav (CabinetView.vue).
// Polled independently of ChatPanel.vue so the badge stays current even while the
// user isn't looking at the chat tab.
const POLL_MS = 15000;

export const useNotificationsStore = defineStore("notifications", () => {
  const total = ref(0);
  const chatUnread = ref(0);
  const systemUnread = ref(0);
  let pollId: ReturnType<typeof setInterval> | null = null;

  async function refresh(): Promise<void> {
    try {
      const summary = await getUnreadSummary();
      chatUnread.value = summary.chat_unread;
      systemUnread.value = summary.system_unread;
      total.value = summary.total;
    } catch {
      // Not authenticated, or a role (admin) with nothing to summarize - leave
      // counts as they were rather than surfacing an error badge.
    }
  }

  function startPolling(): void {
    stopPolling();
    refresh();
    pollId = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, POLL_MS);
  }

  function stopPolling(): void {
    if (pollId) clearInterval(pollId);
    pollId = null;
    total.value = 0;
    chatUnread.value = 0;
    systemUnread.value = 0;
  }

  return { total, chatUnread, systemUnread, refresh, startPolling, stopPolling };
});
