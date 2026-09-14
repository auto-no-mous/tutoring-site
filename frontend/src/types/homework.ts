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
  // Сдачи учеников приходят вместе с заданием - карточка репетитора показывает их сразу.
  submissions: HomeworkSubmission[];
}

export interface HomeworkSubmissionFile {
  id: string;
  file_path: string;
  uploaded_at: string;
}

export interface HomeworkSubmission {
  id: string;
  assignment_id: string;
  student_id: string;
  status: string;
  // Файлов может быть несколько: ученик добавляет ещё один скриншот или убирает лишний.
  files: HomeworkSubmissionFile[];
  comment: string | null;
  submitted_at: string | null;
  student_display_name: string | null;
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
  files: HomeworkSubmissionFile[];
  comment: string | null;
  submitted_at: string | null;
}
