export interface ChatThread {
  id: string;
  type: "individual" | "group";
  tutor_id: string;
  student_id: string | null;
  group_id: string | null;
  display_title: string;
  unread_count: number;
  last_message_preview: string | null;
  last_message_at: string | null;
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  sender_id: string;
  sender_display_name: string;
  content: string | null;
  file_path: string | null;
  created_at: string;
}
