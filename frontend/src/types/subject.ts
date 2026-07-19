export interface Direction {
  id: string;
  subject_id: string;
  name: string;
}

export interface Subject {
  id: string;
  name: string;
  directions: Direction[];
}

export interface TutorSubjectSelection {
  subject_id: string;
  direction_ids: string[];
}

export interface TutorSubject {
  subject_id: string;
  subject_name: string;
  directions: Direction[];
}
