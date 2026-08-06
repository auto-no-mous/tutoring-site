import { apiClient } from "@/api/client";
import type {
  AvailabilityInterval,
  LessonType,
  Slot,
  TutorCatalogItem,
  TutorProfile,
  TutorPublicProfile,
  TutorStudent,
  TutorStudentDetail,
} from "@/types/tutor";
import type { GroupPublic } from "@/types/group";
import type { RatingSummary, Review } from "@/types/stats";
import type { TutorSubject, TutorSubjectSelection } from "@/types/subject";

export interface TutorCatalogPage {
  items: TutorCatalogItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function getCatalog(params: {
  subject_id?: string;
  price_min?: number;
  price_max?: number;
  page?: number;
  page_size?: number;
}) {
  const { data } = await apiClient.get<TutorCatalogPage>("/tutors", { params });
  return data;
}

export async function getPublicProfile(tutorId: string) {
  const { data } = await apiClient.get<TutorPublicProfile>(`/tutors/${tutorId}`);
  return data;
}

export async function getPublicLessonTypes(tutorId: string) {
  const { data } = await apiClient.get<LessonType[]>(`/tutors/${tutorId}/lesson-types`);
  return data;
}

export async function getPublicGroups(tutorId: string) {
  const { data } = await apiClient.get<GroupPublic[]>(`/tutors/${tutorId}/groups`);
  return data;
}

export async function getAvailableDates(tutorId: string, lessonTypeId: string, dateFrom: string, dateTo: string) {
  const { data } = await apiClient.get<string[]>(`/tutors/${tutorId}/availability/dates`, {
    params: { lesson_type_id: lessonTypeId, date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function getDaySlots(tutorId: string, lessonTypeId: string, date: string) {
  const { data } = await apiClient.get<Slot[]>(`/tutors/${tutorId}/availability/slots`, {
    params: { lesson_type_id: lessonTypeId, date },
  });
  return data;
}

export async function getReviews(tutorId: string) {
  const { data } = await apiClient.get<Review[]>(`/tutors/${tutorId}/reviews`);
  return data;
}

export async function getRating(tutorId: string) {
  const { data } = await apiClient.get<RatingSummary>(`/tutors/${tutorId}/rating`);
  return data;
}

export async function createOrUpdateReview(tutorId: string, rating: number, text: string | null) {
  const { data } = await apiClient.post<Review>(`/tutors/${tutorId}/reviews`, { rating, text });
  return data;
}

export async function getMyProfile() {
  const { data } = await apiClient.get<TutorProfile>("/tutors/me");
  return data;
}

export async function updateMyProfile(payload: Partial<TutorProfile>) {
  const { data } = await apiClient.patch<TutorProfile>("/tutors/me", payload);
  return data;
}

export async function uploadMyPhoto(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<TutorProfile>("/tutors/me/photo", form);
  return data;
}

export async function uploadAboutImage(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<{ url: string }>("/tutors/me/about-image", form);
  return data.url;
}

export async function getMyAvailability() {
  const { data } = await apiClient.get<AvailabilityInterval[]>("/tutors/me/availability");
  return data;
}

export async function replaceMyAvailability(intervals: { weekday: number; start_time: string; end_time: string }[]) {
  const { data } = await apiClient.put<AvailabilityInterval[]>("/tutors/me/availability", { intervals });
  return data;
}

export async function getMyLessonTypes() {
  const { data } = await apiClient.get<LessonType[]>("/tutors/me/lesson-types");
  return data;
}

export async function createLessonType(payload: {
  name: string;
  format: "individual" | "group";
  duration_minutes: number;
  price: number;
}) {
  const { data } = await apiClient.post<LessonType>("/tutors/me/lesson-types", payload);
  return data;
}

export async function updateLessonType(id: string, payload: Partial<LessonType>) {
  const { data } = await apiClient.patch<LessonType>(`/tutors/me/lesson-types/${id}`, payload);
  return data;
}

export async function deleteLessonType(id: string) {
  await apiClient.delete(`/tutors/me/lesson-types/${id}`);
}

export async function getMyStudents() {
  const { data } = await apiClient.get<TutorStudent[]>("/tutors/me/students");
  return data;
}

export async function getMyStudentDetail(studentId: string) {
  const { data } = await apiClient.get<TutorStudentDetail>(`/tutors/me/students/${studentId}`);
  return data;
}

export async function getManualBookingDates(durationMinutes: number, dateFrom: string, dateTo: string) {
  const { data } = await apiClient.get<string[]>("/tutors/me/manual-booking/dates", {
    params: { duration_minutes: durationMinutes, date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function getManualBookingSlots(durationMinutes: number, date: string) {
  const { data } = await apiClient.get<Slot[]>("/tutors/me/manual-booking/slots", {
    params: { duration_minutes: durationMinutes, date },
  });
  return data;
}

export async function getMySubjects() {
  const { data } = await apiClient.get<TutorSubject[]>("/tutors/me/subjects");
  return data;
}

export async function replaceMySubjects(selections: TutorSubjectSelection[]) {
  const { data } = await apiClient.put<TutorSubject[]>("/tutors/me/subjects", { selections });
  return data;
}
