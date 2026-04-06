import { client } from './client';

export const studentApi = {
  getProfile: () => client.get('/students/profile/'),
  updateProfile: (data) => client.patch('/students/profile/', data),
  getList: () => client.get('/students/'),
  // Skill assessment (MCQ + RandomForest domain profile)
  getComposedAssessment: () => client.get('/student/assessments/composed/'),
  submitComposedAssessment: (data) => client.post('/student/assessments/composed/submit/', data),
  getAttempts: () => client.get('/student/attempts/'),
  getRecommendedProjects: () => client.get('/student/projects/recommended/'),
  getAssignments: () => client.get('/student/assignments/'),
  getProgressSnapshot: () => client.get('/student/assignments/progress/'),
  acceptProject: (assignmentId) => client.post(`/student/projects/${assignmentId}/accept/`),
  submitProject: (assignmentId, data) => client.post(`/student/assignments/${assignmentId}/submissions/`, data),
  getSubmissionFeedback: (submissionId) => client.get(`/student/submissions/${submissionId}/feedback/`),
};
