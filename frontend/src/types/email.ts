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
