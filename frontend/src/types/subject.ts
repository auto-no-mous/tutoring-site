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

// Public /subjects response. The admin CRUD returns a plain Subject, so the count
// lives here rather than on Subject itself.
export interface CatalogSubject extends Subject {
  tutors_count: number;
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
