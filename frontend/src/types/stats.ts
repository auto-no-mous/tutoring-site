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

export interface ActivityLogEntry {
  id: string;
  event_type: string;
  occurred_at: string;
  lesson_at: string | null;
  format_label: string;
  counterpart_label: string;
  counterpart_name: string;
  duration_minutes: number | null;
  status_label: string;
}

export interface ActivityLogPage {
  entries: ActivityLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export const ACTIVITY_EVENT_GROUPS: { label: string; types: string[] }[] = [
  {
    label: "Индивидуальные занятия",
    types: [
      "lesson_conducted",
      "lesson_student_no_show",
      "lesson_tutor_no_show",
      "lesson_cancelled_by_student",
      "lesson_cancelled_by_tutor",
      "lesson_rescheduled",
    ],
  },
  {
    label: "Групповые занятия",
    types: ["group_lesson_conducted", "group_lesson_student_no_show", "group_lesson_cancelled", "group_lesson_rescheduled"],
  },
  {
    label: "Заявки и участие в группах",
    types: ["group_application_accepted", "group_application_rejected", "group_membership_left", "group_membership_removed"],
  },
];

export const ACTIVITY_EVENT_LABELS: Record<string, string> = {
  lesson_conducted: "Занятие проведено",
  lesson_student_no_show: "Ученик не явился",
  lesson_tutor_no_show: "Репетитор не явился",
  lesson_cancelled_by_student: "Отменено учеником",
  lesson_cancelled_by_tutor: "Отменено репетитором",
  lesson_rescheduled: "Перенесено учеником",
  group_lesson_conducted: "Групповое занятие проведено",
  group_lesson_student_no_show: "Ученик не явился (группа)",
  group_lesson_cancelled: "Групповое занятие отменено",
  group_lesson_rescheduled: "Групповое занятие перенесено",
  group_application_accepted: "Заявка в группу принята",
  group_application_rejected: "Заявка в группу отклонена",
  group_membership_left: "Ученик покинул группу",
  group_membership_removed: "Ученик исключён из группы",
};
