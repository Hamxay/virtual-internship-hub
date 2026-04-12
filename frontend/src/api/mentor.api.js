import { client } from './client';

export const mentorApi = {
  getProfile: () => client.get('/mentors/profile/'),
  updateProfile: (data) => client.put('/mentors/profile/', data),
  getList: () => client.get('/mentors/'),
  getStudents: () => client.get('/students/'),
  /** FR5 — submissions needing mentor review (domain-scoped). */
  getReviewQueue: () => client.get('/mentor/queue/'),
  /** FR5 — { submission_id, mentor_feedback, approved } */
  submitReview: (data) => client.post('/mentor/reviews/', data),
};
