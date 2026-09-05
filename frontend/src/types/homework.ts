export interface HomeworkAssignment {
  id: string;
  tutor_id: string;
  student_id: string | null;
  group_id: string | null;
  title: string | null;
  content_type: string;
  content_url: string | null;
  content_file_path: string | null;
  submission_mode: string;
  due_at: string | null;
  created_at: string;
  status: string;
  student_display_name: string | null;
  group_name: string | null;
}

export interface HomeworkSubmission {
  id: string;
  assignment_id: string;
  student_id: string;
  status: string;
  file_path: string | null;
  comment: string | null;
  submitted_at: string | null;
}

export interface StudentHomework {
  submission_id: string;
  assignment_id: string;
  tutor_id: string;
  group_id: string | null;
  // Может быть пустым: задание бывает одной ссылкой, без названия.
  title: string | null;
  content_type: string;
  content_url: string | null;
  content_file_path: string | null;
  submission_mode: string;
  due_at: string | null;
  status: string;
  file_path: string | null;
  comment: string | null;
  submitted_at: string | null;
}
