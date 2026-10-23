export type EmailDirection = "outbound" | "inbound";
export type EmailKind = "verification" | "password_reset" | "admin" | "inbound" | "other";
export type EmailStatus = "sent" | "failed" | "received";

export interface EmailLogEntry {
  id: string;
  direction: EmailDirection;
  kind: EmailKind;
  status: EmailStatus;
  address_from: string;
  address_to: string;
  subject: string;
  body_preview: string;
  user_id: string | null;
  sent_by_id: string | null;
  error: string | null;
  created_at: string;
}

// Полный текст письма - отдельным запросом по кнопке «Показать полностью». null у
// писем, для которых журнал хранил только превью (до 23.10.2026).
export interface EmailLogDetail extends EmailLogEntry {
  body_text: string | null;
}

export interface EmailLogPage {
  entries: EmailLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface EmailStats {
  sent_24h: number;
  failed_24h: number;
  sent_30d: number;
  failed_30d: number;
  received_30d: number;
  by_kind: Record<string, number>;
  last_sent_at: string | null;
}

export interface AdminEmailSendResult {
  sent: number;
  failed: number;
  skipped: string[];
}
