import { apiClient } from "@/api/client";
import type { Booking } from "@/types/booking";
import type { Group, GroupApplication, GroupMembership } from "@/types/group";
import type { NotificationTemplate } from "@/types/notification";
import type { AdminEmailSendResult, EmailLogPage, EmailStats } from "@/types/email";
import type { BlogPostAdmin, BlogPostPayload } from "@/types/blog";
import type { Direction, Subject } from "@/types/subject";
import type { Slot, TutorProfile } from "@/types/tutor";
import type { User } from "@/types/user";

// --- Tutors -----------------------------------------------------------------

export async function listTutors() {
  const { data } = await apiClient.get<TutorProfile[]>("/admin/tutors");
  return data;
}

export interface AdminTutorUpdatePayload {
  first_name?: string;
  last_name?: string;
  patronymic?: string | null;
  email?: string;
  is_active?: boolean;
  about?: string;
  is_hidden?: boolean;
  cancel_min_hours_before?: number;
  cancel_max_per_month?: number;
  reschedule_min_hours_before?: number;
  reschedule_max_per_month?: number;
}

export async function updateTutor(id: string, payload: AdminTutorUpdatePayload) {
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

export interface AdminStudentUpdatePayload {
  first_name?: string;
  last_name?: string;
  patronymic?: string | null;
  email?: string;
  grade?: number | null;
  timezone?: string;
  is_active?: boolean;
}

export async function updateStudent(id: string, payload: AdminStudentUpdatePayload) {
  const { data } = await apiClient.patch<User>(`/admin/students/${id}`, payload);
  return data;
}

export async function deleteStudent(id: string) {
  await apiClient.delete(`/admin/students/${id}`);
}

// --- Пользователи (любая роль) --------------------------------------------------

// По user_id, а не по роли: у TutorProfile есть user_id, так что обе вкладки админки
// зовут одну и ту же ручку. Отзывает все refresh-токены пользователя и снимает
// блокировку после неудачных попыток входа - см. backend admin_service.
export async function resetUserPassword(userId: string, newPassword: string) {
  await apiClient.post(`/admin/users/${userId}/password`, { new_password: newPassword });
}

// --- Bookings -----------------------------------------------------------------

export interface BookingPage {
  items: Booking[];
  total: number;
  page: number;
  page_size: number;
}

export async function listBookings(params?: {
  tutor_id?: string;
  student_id?: string;
  date_from?: string;
  date_to?: string;
  subject_id?: string;
  direction_id?: string;
  grade?: number;
  page?: number;
  page_size?: number;
}) {
  const { data } = await apiClient.get<BookingPage>("/admin/bookings", { params });
  return data;
}

export async function updateBooking(id: string, payload: Partial<{ meeting_link: string | null; notes: string | null }>) {
  const { data } = await apiClient.patch<Booking>(`/admin/bookings/${id}`, payload);
  return data;
}

export async function deleteBooking(id: string) {
  await apiClient.delete(`/admin/bookings/${id}`);
}

export async function rescheduleBooking(id: string, newStartAt: string, durationMinutes?: number) {
  const { data } = await apiClient.post<Booking>(`/admin/bookings/${id}/reschedule`, {
    new_start_at: newStartAt,
    duration_minutes: durationMinutes,
  });
  return data;
}

export async function getAdminRescheduleDates(bookingId: string, dateFrom: string, dateTo: string, durationMinutes?: number) {
  const { data } = await apiClient.get<string[]>(`/admin/bookings/${bookingId}/reschedule/dates`, {
    params: { date_from: dateFrom, date_to: dateTo, duration_minutes: durationMinutes },
  });
  return data;
}

export async function getAdminRescheduleSlots(bookingId: string, date: string, durationMinutes?: number) {
  const { data } = await apiClient.get<Slot[]>(`/admin/bookings/${bookingId}/reschedule/slots`, {
    params: { date, duration_minutes: durationMinutes },
  });
  return data;
}

// --- Groups -----------------------------------------------------------------

export async function listGroups() {
  const { data } = await apiClient.get<Group[]>("/admin/groups");
  return data;
}

export async function updateGroup(
  id: string,
  payload: Partial<{ name: string; capacity: number; meeting_link: string | null; is_active: boolean }>,
) {
  const { data } = await apiClient.patch<Group>(`/admin/groups/${id}`, payload);
  return data;
}

export async function deleteGroup(id: string) {
  await apiClient.delete(`/admin/groups/${id}`);
}

export async function reassignGroupTutor(id: string, tutorId: string, lessonTypeId: string) {
  const { data } = await apiClient.post<Group>(`/admin/groups/${id}/reassign-tutor`, {
    tutor_id: tutorId,
    lesson_type_id: lessonTypeId,
  });
  return data;
}

export async function listGroupMembers(groupId: string) {
  const { data } = await apiClient.get<GroupMembership[]>(`/admin/groups/${groupId}/members`);
  return data;
}

export async function addGroupMember(groupId: string, studentId: string) {
  const { data } = await apiClient.post<GroupMembership>(`/admin/groups/${groupId}/members`, { student_id: studentId });
  return data;
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

// --- Notification templates --------------------------------------------------

export async function listNotificationTemplates() {
  const { data } = await apiClient.get<NotificationTemplate[]>("/admin/notification-templates");
  return data;
}

export async function updateNotificationTemplate(id: string, title: string, body: string) {
  const { data } = await apiClient.put<NotificationTemplate>(`/admin/notification-templates/${id}`, { title, body });
  return data;
}

// --- Почта ------------------------------------------------------------------

export interface EmailLogFilters {
  direction?: string;
  status?: string;
  kind?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export async function listEmails(filters: EmailLogFilters = {}) {
  const { data } = await apiClient.get<EmailLogPage>("/admin/emails", { params: filters });
  return data;
}

export async function getEmailStats() {
  const { data } = await apiClient.get<EmailStats>("/admin/emails/stats");
  return data;
}

export async function sendAdminEmail(payload: {
  user_ids: string[];
  emails: string[];
  subject: string;
  body: string;
}) {
  const { data } = await apiClient.post<AdminEmailSendResult>("/admin/emails/send", payload);
  return data;
}

// --- Blog --------------------------------------------------------------------

export async function listBlogPostsAdmin() {
  const { data } = await apiClient.get<BlogPostAdmin[]>("/admin/blog");
  return data;
}

export async function createBlogPost(payload: Partial<BlogPostPayload>) {
  const { data } = await apiClient.post<BlogPostAdmin>("/admin/blog", payload);
  return data;
}

export async function updateBlogPost(id: string, payload: Partial<BlogPostPayload>) {
  const { data } = await apiClient.patch<BlogPostAdmin>(`/admin/blog/${id}`, payload);
  return data;
}

export async function deleteBlogPost(id: string) {
  await apiClient.delete(`/admin/blog/${id}`);
}

export async function uploadBlogImage(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<{ url: string }>("/admin/blog/images", form);
  return data.url;
}
