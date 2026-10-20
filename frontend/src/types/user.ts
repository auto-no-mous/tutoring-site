export type UserRole = "tutor" | "student" | "admin";
export type NotificationChannel = "telegram" | "email";

// Настройки одного канала: сам канал, отдельные события и за сколько минут
// напоминать о занятии. Остальные уведомления (сообщения в чате, заявки в группы)
// идут в канал, пока он включён.
export interface ChannelNotificationSettings {
  enabled: boolean;
  new_booking: boolean;
  schedule_change: boolean;
  reminder: boolean;
  reminder_lead_minutes: number;
}

export type NotificationSettings = Record<NotificationChannel, ChannelNotificationSettings>;

export interface User {
  id: string;
  email: string | null;
  display_name: string;
  first_name: string;
  last_name: string;
  patronymic: string | null;
  grade: number | null;
  // Аватар аккаунта. У репетитора фото анкеты - отдельное поле TutorProfile.photo_url.
  photo_url: string | null;
  role: UserRole;
  email_verified: boolean;
  is_active: boolean;
  timezone: string;
  telegram_chat_id: string | null;
  notification_settings: NotificationSettings;
  // Чем можно войти в аккаунт: "password" и/или провайдеры ("vk", "yandex").
  auth_providers: string[];
  created_at: string;
}
