export type UserRole = "tutor" | "student" | "admin";

export interface User {
  id: string;
  email: string | null;
  display_name: string;
  first_name: string;
  last_name: string;
  patronymic: string | null;
  role: UserRole;
  email_verified: boolean;
  is_active: boolean;
  timezone: string;
  telegram_chat_id: string | null;
  email_notifications_enabled: boolean;
  created_at: string;
}
