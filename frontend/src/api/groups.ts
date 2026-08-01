import { apiClient } from "@/api/client";
import type {
  Group,
  GroupApplication,
  GroupAttendanceEntry,
  GroupMembership,
  GroupOccurrence,
  GroupScheduleSlot,
} from "@/types/group";

export async function createGroup(payload: {
  name: string;
  lesson_type_id: string;
  capacity: number;
  meeting_link?: string | null;
  schedule_slots: GroupScheduleSlot[];
}) {
  const { data } = await apiClient.post<Group>("/groups", payload);
  return data;
}

export async function listMyGroups() {
  const { data } = await apiClient.get<Group[]>("/groups/tutor/me");
  return data;
}

export async function updateGroup(id: string, payload: Partial<Group>) {
  const { data } = await apiClient.patch<Group>(`/groups/${id}`, payload);
  return data;
}

export async function replaceSchedule(id: string, slots: GroupScheduleSlot[]) {
  const { data } = await apiClient.put<Group>(`/groups/${id}/schedule`, slots);
  return data;
}

export async function listApplications(groupId: string) {
  const { data } = await apiClient.get<GroupApplication[]>(`/groups/${groupId}/applications`);
  return data;
}

export async function acceptApplication(groupId: string, applicationId: string) {
  const { data } = await apiClient.post<GroupMembership>(`/groups/${groupId}/applications/${applicationId}/accept`);
  return data;
}

export async function rejectApplication(groupId: string, applicationId: string) {
  const { data } = await apiClient.post<GroupApplication>(`/groups/${groupId}/applications/${applicationId}/reject`);
  return data;
}

export async function listMembers(groupId: string) {
  const { data } = await apiClient.get<GroupMembership[]>(`/groups/${groupId}/members`);
  return data;
}

export async function removeMember(groupId: string, studentId: string) {
  const { data } = await apiClient.delete<GroupMembership>(`/groups/${groupId}/members/${studentId}`);
  return data;
}

export async function listOccurrences(groupId: string) {
  const { data } = await apiClient.get<GroupOccurrence[]>(`/groups/${groupId}/occurrences`);
  return data;
}

export async function createOccurrence(groupId: string, startAt: string, endAt: string) {
  const { data } = await apiClient.post<GroupOccurrence>(`/groups/${groupId}/occurrences`, {
    start_at: startAt,
    end_at: endAt,
  });
  return data;
}

export async function updateOccurrence(
  groupId: string,
  occurrenceId: string,
  payload: { start_at?: string; end_at?: string; status?: string },
) {
  const { data } = await apiClient.patch<GroupOccurrence>(`/groups/${groupId}/occurrences/${occurrenceId}`, payload);
  return data;
}

export async function deleteOccurrence(groupId: string, occurrenceId: string) {
  await apiClient.delete(`/groups/${groupId}/occurrences/${occurrenceId}`);
}

export async function applyToGroup(groupId: string, message?: string) {
  const { data } = await apiClient.post<GroupApplication>(`/groups/${groupId}/apply`, { message: message ?? null });
  return data;
}

export async function leaveGroup(groupId: string) {
  const { data } = await apiClient.post<GroupMembership>(`/groups/${groupId}/leave`);
  return data;
}

export async function myMemberships() {
  const { data } = await apiClient.get<GroupMembership[]>("/groups/me");
  return data;
}

export async function myApplications() {
  const { data } = await apiClient.get<GroupApplication[]>("/groups/me/applications");
  return data;
}

export async function getOccurrenceAttendance(groupId: string, occurrenceId: string) {
  const { data } = await apiClient.get<GroupAttendanceEntry[]>(
    `/groups/${groupId}/occurrences/${occurrenceId}/attendance`,
  );
  return data;
}

export async function setOccurrenceAttendance(
  groupId: string,
  occurrenceId: string,
  entries: { student_id: string; outcome: string }[],
) {
  const { data } = await apiClient.put<GroupAttendanceEntry[]>(
    `/groups/${groupId}/occurrences/${occurrenceId}/attendance`,
    { entries },
  );
  return data;
}
