export interface Booking {
  id: string;
  tutor_id: string;
  student_id: string | null;
  lesson_type_id: string | null;
  start_at: string;
  end_at: string;
  status: string;
  is_manual_block: boolean;
  booked_by: string;
  meeting_link: string | null;
  notes: string | null;
  recurring_series_id: string | null;
  cancelled_by: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  rescheduled_from_id: string | null;
  outcome: string | null;
  student_display_name?: string | null;
  series_is_active?: boolean | null;
  lesson_type_name?: string | null;
  tutor_display_name?: string | null;
}

export interface RecurringSeriesDetail {
  id: string;
  tutor_id: string;
  student_id: string;
  lesson_type_id: string;
  weekday: number;
  start_time: string;
  is_active: boolean;
  lesson_type_name: string;
  tutor_display_name: string;
}
