export interface TutorStats {
  total_lessons_held: number;
  homeworks_done: number;
  unique_students_this_month: number;
}

export interface StudentStats {
  lessons_completed: number;
  homework_total: number;
  homework_done: number;
  homework_completion_rate: number;
}

export interface Review {
  id: string;
  tutor_id: string;
  student_id: string;
  rating: number;
  text: string | null;
  created_at: string;
  updated_at: string;
  student_display_name: string;
}

export interface RatingSummary {
  average: number | null;
  count: number;
}
