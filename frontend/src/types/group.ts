export interface GroupScheduleSlot {
  id?: string;
  weekday: number;
  start_time: string;
}

export interface Group {
  id: string;
  tutor_id: string;
  lesson_type_id: string;
  name: string;
  capacity: number;
  meeting_link: string | null;
  is_active: boolean;
  schedule_slots: GroupScheduleSlot[];
  member_count: number;
}

export interface GroupPublic {
  id: string;
  tutor_id: string;
  name: string;
  capacity: number;
  member_count: number;
  price: number;
  duration_minutes: number;
  schedule_slots: GroupScheduleSlot[];
}

export interface GroupApplication {
  id: string;
  group_id: string;
  student_id: string;
  status: string;
  message: string | null;
  created_at: string;
  decided_at: string | null;
  group_name: string;
  tutor_display_name: string;
}

export interface GroupMembership {
  id: string;
  group_id: string;
  student_id: string;
  status: string;
  joined_at: string;
  left_at: string | null;
  left_by: string | null;
  group_name: string;
  tutor_display_name: string;
}

export interface GroupOccurrence {
  id: string;
  group_id: string;
  start_at: string;
  end_at: string;
  status: string;
  original_start_at: string | null;
}

export interface GroupAttendanceEntry {
  student_id: string;
  student_display_name: string;
  outcome: string;
}
