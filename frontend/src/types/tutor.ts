import type { TutorSubject } from "@/types/subject";

export interface TutorExtraLink {
  label: string;
  url: string;
}

export interface TutorProfile {
  id: string;
  user_id: string;
  photo_url: string | null;
  about: string;
  is_hidden: boolean;
  slug: string | null;
  telegram_url: string | null;
  vk_url: string | null;
  youtube_url: string | null;
  video_url: string | null;
  extra_links: TutorExtraLink[];
  slot_granularity_minutes: number;
  break_between_lessons_minutes: number;
  min_lead_time_hours: number;
  cancel_min_hours_before: number;
  cancel_max_per_month: number;
  reschedule_min_hours_before: number;
  reschedule_max_per_month: number;
  allow_individual_bookings: boolean;
  allow_group_bookings: boolean;
  display_name: string | null;
  is_active: boolean | null;
  // Populated only for own profile / admin contexts - see backend
  // api/v1/tutors.py and api/v1/admin.py's _to_profile_out.
  first_name?: string | null;
  last_name?: string | null;
  patronymic?: string | null;
  email?: string | null;
  email_verified?: boolean | null;
  // Populated only by the admin tutor listing - see backend api/v1/admin.py::list_tutors.
  subjects?: TutorSubject[];
}

export interface TutorCatalogItem {
  id: string;
  user_id: string;
  display_name: string;
  // "Имя Отчество" only (no surname) - catalog card format.
  name_patronymic: string;
  photo_url: string | null;
  slug: string | null;
  subjects: string[];
  hourly_price: number | null;
  avg_rating: number | null;
  reviews_count: number;
  about_snippet: string | null;
  show_individual_booking: boolean;
  show_group_booking: boolean;
}

export interface TutorPublicProfile {
  id: string;
  user_id: string;
  display_name: string;
  photo_url: string | null;
  about: string;
  telegram_url: string | null;
  vk_url: string | null;
  youtube_url: string | null;
  video_url: string | null;
  // Player URL built by the backend from video_url (app/utils/video.py) - rendered
  // as an <iframe src> as-is, the frontend never parses the tutor's link itself.
  video_embed_url: string | null;
  extra_links: TutorExtraLink[];
  subjects: TutorSubject[];
  avg_rating: number | null;
  reviews_count: number;
  // Already combine the tutor's toggle with whether they have an active lesson type
  // of that format - see backend api/v1/tutors.py::get_public_profile.
  show_individual_booking: boolean;
  show_group_booking: boolean;
}

export interface TutorStudent {
  id: string;
  first_name: string;
  last_name: string;
  grade: number | null;
  last_lesson_at: string | null;
}

export interface StudentGroupMembership {
  group_id: string;
  group_name: string;
  status: string;
  joined_at: string;
  left_at: string | null;
}

export interface TutorStudentDetail {
  id: string;
  first_name: string;
  last_name: string;
  patronymic: string | null;
  grade: number | null;
  email: string | null;
  groups: StudentGroupMembership[];
}

export interface LessonType {
  id: string;
  tutor_id: string;
  name: string;
  format: "individual" | "group";
  duration_minutes: number;
  price: number;
  is_active: boolean;
}

export interface AvailabilityInterval {
  id: string;
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface Slot {
  start_at: string;
  end_at: string;
  available: boolean;
}
