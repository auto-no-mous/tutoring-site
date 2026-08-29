import { apiClient } from "@/api/client";
import type { User } from "@/types/user";

export interface UserSettingsUpdate {
  first_name?: string;
  last_name?: string;
  patronymic?: string | null;
  grade?: number | null;
  email?: string;
  timezone?: string;
  telegram_chat_id?: string | null;
  notification_channel?: string;
  reminder_lead_minutes?: number;
}

export async function updateMySettings(payload: UserSettingsUpdate) {
  const { data } = await apiClient.patch<User>("/auth/me", payload);
  return data;
}

/** Аватар аккаунта. Файл приходит уже обрезанным квадратом из PhotoCropModal. */
export async function uploadMyPhoto(file: Blob, filename = "photo.jpg") {
  const form = new FormData();
  form.append("file", file, filename);
  const { data } = await apiClient.post<User>("/auth/me/photo", form);
  return data;
}

export async function deleteMyPhoto() {
  const { data } = await apiClient.delete<User>("/auth/me/photo");
  return data;
}

export async function verifyEmail(token: string) {
  const { data } = await apiClient.post<User>("/auth/verify-email", { token });
  return data;
}

export async function resendVerificationEmail() {
  await apiClient.post("/auth/verify-email/resend");
}

export async function requestPasswordReset(email: string) {
  await apiClient.post("/auth/password-reset/request", { email });
}

export async function confirmPasswordReset(token: string, newPassword: string) {
  await apiClient.post("/auth/password-reset/confirm", { token, new_password: newPassword });
}

export interface TelegramLinkToken {
  token: string;
  deep_link: string | null;
}

export async function getTelegramLinkToken() {
  const { data } = await apiClient.post<TelegramLinkToken>("/auth/me/telegram-link-token");
  return data;
}
