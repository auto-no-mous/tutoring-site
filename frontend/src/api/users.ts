import { apiClient } from "@/api/client";
import type { User } from "@/types/user";

export interface UserSettingsUpdate {
  first_name?: string;
  last_name?: string;
  patronymic?: string | null;
  email?: string;
  timezone?: string;
  telegram_chat_id?: string | null;
  email_notifications_enabled?: boolean;
}

export async function updateMySettings(payload: UserSettingsUpdate) {
  const { data } = await apiClient.patch<User>("/auth/me", payload);
  return data;
}
