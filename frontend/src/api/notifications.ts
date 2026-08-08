import { apiClient } from "@/api/client";
import type { SystemNotification, UnreadSummary } from "@/types/notification";

export async function listSystemNotifications() {
  const { data } = await apiClient.get<SystemNotification[]>("/notifications/system");
  return data;
}

export async function markSystemNotificationsRead() {
  await apiClient.post("/notifications/system/read");
}

export async function getUnreadSummary() {
  const { data } = await apiClient.get<UnreadSummary>("/notifications/unread-summary");
  return data;
}
