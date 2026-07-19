import { apiClient } from "@/api/client";
import type { Subject } from "@/types/subject";

export async function listSubjects() {
  const { data } = await apiClient.get<Subject[]>("/subjects");
  return data;
}
