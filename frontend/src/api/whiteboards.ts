import { apiClient } from "@/api/client";

export interface Whiteboard {
  id: string;
  tutor_id: string;
  student_id: string | null;
  group_id: string | null;
  url: string;
  title: string | null;
  last_used_at: string;
}

export interface WhiteboardPayload {
  student_id?: string | null;
  group_id?: string | null;
  url: string;
  title?: string | null;
}

/** Все доски, видимые пользователю, одним запросом: они привязаны к паре
 * репетитор-ученик или к группе, а не к занятию, поэтому карточки разбирают общий
 * список сами вместо запроса на каждую. */
export async function listMyWhiteboards() {
  const { data } = await apiClient.get<Whiteboard[]>("/whiteboards/my");
  return data;
}

export async function createWhiteboard(payload: WhiteboardPayload) {
  const { data } = await apiClient.post<Whiteboard>("/whiteboards", payload);
  return data;
}

export async function updateWhiteboard(
  boardId: string,
  payload: { url?: string; title?: string | null },
) {
  const { data } = await apiClient.patch<Whiteboard>(`/whiteboards/${boardId}`, payload);
  return data;
}

export async function deleteWhiteboard(boardId: string) {
  await apiClient.delete(`/whiteboards/${boardId}`);
}

/** Отмечает доску открытой - она поднимается наверх списка у обеих сторон занятия. */
export async function markWhiteboardUsed(boardId: string) {
  const { data } = await apiClient.post<Whiteboard>(`/whiteboards/${boardId}/use`);
  return data;
}
