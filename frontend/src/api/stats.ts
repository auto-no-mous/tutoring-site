import { apiClient } from "@/api/client";
import type { ActivityLogPage, StudentStats, TutorStats } from "@/types/stats";

export async function getTutorStats() {
  const { data } = await apiClient.get<TutorStats>("/stats/tutor/me");
  return data;
}

export async function getStudentStats() {
  const { data } = await apiClient.get<StudentStats>("/stats/student/me");
  return data;
}

export interface ActivityLogParams {
  event_types?: string[];
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function getTutorLog(params: ActivityLogParams) {
  const { data } = await apiClient.get<ActivityLogPage>("/stats/tutor/me/log", { params });
  return data;
}

export async function getStudentLog(params: ActivityLogParams) {
  const { data } = await apiClient.get<ActivityLogPage>("/stats/student/me/log", { params });
  return data;
}
