import { apiClient } from "@/api/client";
import type { ChatMessage, ChatThread } from "@/types/chat";

export async function listThreads() {
  const { data } = await apiClient.get<ChatThread[]>("/chat/threads");
  return data;
}

export async function openThreadWithStudent(studentId: string) {
  const { data } = await apiClient.post<ChatThread>(`/chat/threads/with-student/${studentId}`);
  return data;
}

export async function openThreadWithTutor(tutorId: string) {
  const { data } = await apiClient.post<ChatThread>(`/chat/threads/with-tutor/${tutorId}`);
  return data;
}

export async function getGroupThread(groupId: string) {
  const { data } = await apiClient.get<ChatThread>(`/chat/threads/group/${groupId}`);
  return data;
}

export async function listMessages(threadId: string) {
  const { data } = await apiClient.get<ChatMessage[]>(`/chat/threads/${threadId}/messages`);
  return data;
}

export async function sendMessage(threadId: string, content?: string, file?: File) {
  const form = new FormData();
  if (content) form.append("content", content);
  if (file) form.append("file", file);
  const { data } = await apiClient.post<ChatMessage>(`/chat/threads/${threadId}/messages`, form);
  return data;
}
