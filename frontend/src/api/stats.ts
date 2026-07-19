import { apiClient } from "@/api/client";
import type { StudentStats, TutorStats } from "@/types/stats";

export async function getTutorStats() {
  const { data } = await apiClient.get<TutorStats>("/stats/tutor/me");
  return data;
}

export async function getStudentStats() {
  const { data } = await apiClient.get<StudentStats>("/stats/student/me");
  return data;
}
