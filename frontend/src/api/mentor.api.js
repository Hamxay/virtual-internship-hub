import { client } from './client';

export const mentorApi = {
  getProfile: () => client.get('/mentors/profile/'),
  updateProfile: (data) => client.put('/mentors/profile/', data),
  getList: () => client.get('/mentors/'),
  getStudents: () => client.get('/students/'),
  getReviewQueue: () => client.get('/mentor/queue/'),
  submitReview: (data) => client.post('/mentor/reviews/', data),
};
