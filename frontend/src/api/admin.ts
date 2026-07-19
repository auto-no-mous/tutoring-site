import { apiClient } from "@/api/client";
import type { Booking } from "@/types/booking";
import type { Group, GroupApplication, GroupMembership } from "@/types/group";
import type { Direction, Subject } from "@/types/subject";
import type { TutorProfile } from "@/types/tutor";
import type { User } from "@/types/user";

// --- Tutors -----------------------------------------------------------------

export async function listTutors() {
  const { data } = await apiClient.get<TutorProfile[]>("/admin/tutors");
  return data;
}

export async function updateTutor(
  id: string,
  payload: Partial<{ first_name: string; last_name: string; patronymic: string | null; is_active: boolean; about: string; is_hidden: boolean }>,
) {
  const { data } = await apiClient.patch<TutorProfile>(`/admin/tutors/${id}`, payload);
  return data;
}

export async function deleteTutor(id: string) {
  await apiClient.delete(`/admin/tutors/${id}`);
}

// --- Students -----------------------------------------------------------------

export async function listStudents() {
  const { data } = await apiClient.get<User[]>("/admin/students");
  return data;
}

export async function updateStudent(
  id: string,
  payload: Partial<{ first_name: string; last_name: string; patronymic: string | null; email: string; is_active: boolean }>,
) {
  const { data } = await apiClient.patch<User>(`/admin/students/${id}`, payload);
  return data;
}

export async function deleteStudent(id: string) {
  await apiClient.delete(`/admin/students/${id}`);
}

// --- Bookings -----------------------------------------------------------------

export async function listBookings(params?: { tutor_id?: string; student_id?: string }) {
  const { data } = await apiClient.get<Booking[]>("/admin/bookings", { params });
  return data;
}

export async function updateBooking(id: string, payload: Partial<{ meeting_link: string | null; notes: string | null }>) {
  const { data } = await apiClient.patch<Booking>(`/admin/bookings/${id}`, payload);
  return data;
}

export async function deleteBooking(id: string) {
  await apiClient.delete(`/admin/bookings/${id}`);
}

// --- Groups -----------------------------------------------------------------

export async function listGroups() {
  const { data } = await apiClient.get<Group[]>("/admin/groups");
  return data;
}

export async function updateGroup(id: string, payload: Partial<{ name: string; capacity: number; is_active: boolean }>) {
  const { data } = await apiClient.patch<Group>(`/admin/groups/${id}`, payload);
  return data;
}

export async function deleteGroup(id: string) {
  await apiClient.delete(`/admin/groups/${id}`);
}

export async function listGroupApplications(groupId: string) {
  const { data } = await apiClient.get<GroupApplication[]>(`/admin/groups/${groupId}/applications`);
  return data;
}

export async function acceptGroupApplication(groupId: string, applicationId: string) {
  const { data } = await apiClient.post<GroupMembership>(`/admin/groups/${groupId}/applications/${applicationId}/accept`);
  return data;
}

export async function rejectGroupApplication(groupId: string, applicationId: string) {
  const { data } = await apiClient.post<GroupApplication>(`/admin/groups/${groupId}/applications/${applicationId}/reject`);
  return data;
}

export async function removeGroupMember(groupId: string, studentId: string) {
  const { data } = await apiClient.delete<GroupMembership>(`/admin/groups/${groupId}/members/${studentId}`);
  return data;
}

// --- Subjects/directions -----------------------------------------------------

export async function listSubjectsAdmin() {
  const { data } = await apiClient.get<Subject[]>("/admin/subjects");
  return data;
}

export async function createSubject(name: string) {
  const { data } = await apiClient.post<Subject>("/admin/subjects", { name });
  return data;
}

export async function updateSubject(id: string, name: string) {
  const { data } = await apiClient.patch<Subject>(`/admin/subjects/${id}`, { name });
  return data;
}

export async function deleteSubject(id: string) {
  await apiClient.delete(`/admin/subjects/${id}`);
}

export async function createDirection(subjectId: string, name: string) {
  const { data } = await apiClient.post<Direction>(`/admin/subjects/${subjectId}/directions`, { name });
  return data;
}

export async function updateDirection(id: string, name: string) {
  const { data } = await apiClient.patch<Direction>(`/admin/directions/${id}`, { name });
  return data;
}

export async function deleteDirection(id: string) {
  await apiClient.delete(`/admin/directions/${id}`);
}
