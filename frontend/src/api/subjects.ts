import { apiClient } from "@/api/client";
import type { CatalogSubject } from "@/types/subject";

export async function listSubjects() {
  const { data } = await apiClient.get<CatalogSubject[]>("/subjects");
  return data;
}
