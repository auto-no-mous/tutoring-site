import { apiClient } from "@/api/client";
import type { HomeworkAssignment, HomeworkSubmission, StudentHomework } from "@/types/homework";

export interface CreateHomeworkPayload {
  title: string;
  submission_mode: "mark_done" | "file_upload";
  student_id?: string;
  group_id?: string;
  content_url?: string;
  due_at?: string;
  file?: File;
}

export async function createHomework(payload: CreateHomeworkPayload) {
  const form = new FormData();
  form.append("title", payload.title);
  form.append("submission_mode", payload.submission_mode);
  if (payload.student_id) form.append("student_id", payload.student_id);
  if (payload.group_id) form.append("group_id", payload.group_id);
  if (payload.content_url) form.append("content_url", payload.content_url);
  if (payload.due_at) form.append("due_at", payload.due_at);
  if (payload.file) form.append("file", payload.file);
  const { data } = await apiClient.post<HomeworkAssignment>("/homework", form);
  return data;
}

export async function listMyAssignments() {
  const { data } = await apiClient.get<HomeworkAssignment[]>("/homework/tutor/me");
  return data;
}

export async function listSubmissions(assignmentId: string) {
  const { data } = await apiClient.get<HomeworkSubmission[]>(`/homework/${assignmentId}/submissions`);
  return data;
}

export async function deleteAssignment(assignmentId: string) {
  await apiClient.delete(`/homework/${assignmentId}`);
}

export async function myHomework() {
  const { data } = await apiClient.get<StudentHomework[]>("/homework/me");
  return data;
}

export async function markDone(submissionId: string) {
  const { data } = await apiClient.post<HomeworkSubmission>(`/homework/submissions/${submissionId}/done`);
  return data;
}

export async function uploadSubmission(submissionId: string, file: File, comment?: string) {
  const form = new FormData();
  form.append("file", file);
  if (comment) form.append("comment", comment);
  const { data } = await apiClient.post<HomeworkSubmission>(`/homework/submissions/${submissionId}/upload`, form);
  return data;
}

export async function getMyStudentsHomeworkStatus() {
  const { data } = await apiClient.get<Record<string, string>>("/homework/tutor/me/student-status");
  return data;
}

export async function getStudentHomeworkForTutor(studentId: string) {
  const { data } = await apiClient.get<StudentHomework[]>(`/homework/tutor/me/students/${studentId}`);
  return data;
}

export async function setSubmissionStatus(submissionId: string, status: string) {
  const { data } = await apiClient.patch<HomeworkSubmission>(`/homework/submissions/${submissionId}/status`, { status });
  return data;
}
