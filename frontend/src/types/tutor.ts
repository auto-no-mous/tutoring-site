import type { TutorSubject } from "@/types/subject";

export interface TutorProfile {
  id: string;
  user_id: string;
  photo_url: string | null;
  about: string;
  achievements: string;
  is_hidden: boolean;
  slot_granularity_minutes: number;
  break_between_lessons_minutes: number;
  min_lead_time_hours: number;
  cancel_min_hours_before: number;
  cancel_max_per_month: number;
  reschedule_min_hours_before: number;
  reschedule_max_per_month: number;
  display_name: string | null;
  is_active: boolean | null;
}

export interface TutorCatalogItem {
  id: string;
  user_id: string;
  display_name: string;
  // "Имя Отчество" only (no surname) - catalog card format.
  name_patronymic: string;
  photo_url: string | null;
  subjects: string[];
  hourly_price: number | null;
  avg_rating: number | null;
  reviews_count: number;
}

export interface TutorPublicProfile {
  id: string;
  user_id: string;
  display_name: string;
  photo_url: string | null;
  about: string;
  achievements: string;
  subjects: TutorSubject[];
  avg_rating: number | null;
  reviews_count: number;
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
