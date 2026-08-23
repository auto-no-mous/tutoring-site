export type UserRole = "tutor" | "student" | "admin";
export type NotificationChannel = "off" | "email" | "telegram" | "both";

export interface User {
  id: string;
  email: string | null;
  display_name: string;
  first_name: string;
  last_name: string;
  patronymic: string | null;
  grade: number | null;
  role: UserRole;
  email_verified: boolean;
  is_active: boolean;
  timezone: string;
  telegram_chat_id: string | null;
  // Куда слать уведомления и напоминания: off / email / telegram / both.
  notification_channel: NotificationChannel;
  reminder_lead_minutes: number;
  created_at: string;
}
