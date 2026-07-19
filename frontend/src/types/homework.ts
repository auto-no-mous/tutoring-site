export interface HomeworkAssignment {
  id: string;
  tutor_id: string;
  student_id: string | null;
  group_id: string | null;
  title: string;
  content_type: string;
  content_url: string | null;
  content_file_path: string | null;
  submission_mode: string;
  due_at: string | null;
  created_at: string;
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
  title: string;
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
