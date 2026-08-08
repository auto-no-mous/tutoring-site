export interface SystemNotification {
  id: string;
  event_type: string;
  title: string;
  body: string;
  created_at: string;
  read_at: string | null;
}

export interface UnreadSummary {
  chat_unread: number;
  system_unread: number;
  total: number;
}

export interface NotificationTemplate {
  id: string;
  event_type: string;
  role: string;
  title: string;
  body: string;
}
