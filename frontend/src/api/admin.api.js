import { client } from './client';

export const adminApi = {
  createAdministrator: (data) => client.post('/admin/administrators/', data),

  // Users (students and mentors only; paginated)
  getStudents: (params) => client.get('/admin/users/students/', { params: params || {} }),
  getMentors: (params) => client.get('/admin/users/mentors/', { params: params || {} }),

  // Domains CRUD (admin only; paginated)
  getDomainsAdmin: (params) => client.get('/admin/domains/', { params: params || {} }),
  createDomain: (data) => client.post('/admin/domains/', data),
  updateDomain: (id, data) => client.patch(`/admin/domains/${id}/`, data),
  deleteDomain: (id) => client.delete(`/admin/domains/${id}/`),

  // Domain questions (MCQs per domain; 5 per page)
  getDomainQuestionCounts: () => client.get('/admin/domains/question-counts/'),
  getDomainQuestions: (domainId, params) => client.get(`/admin/domains/${domainId}/questions/`, { params: params || {} }),
  createQuestion: (domainId, data) => client.post(`/admin/domains/${domainId}/questions/`, data),
  updateQuestion: (domainId, questionId, data) =>
    client.patch(`/admin/domains/${domainId}/questions/${questionId}/`, data),
  deleteQuestion: (domainId, questionId) =>
    client.delete(`/admin/domains/${domainId}/questions/${questionId}/`),

  // Project templates and AI evaluation
  getProjectTemplates: (params) => client.get('/admin/project-templates/', { params: params || {} }),
  createProjectTemplate: (data) => client.post('/admin/project-templates/', data),
  updateProjectTemplate: (id, data) => client.patch(`/admin/project-templates/${id}/`, data),
  deleteProjectTemplate: (id) => client.delete(`/admin/project-templates/${id}/`),
  assignProject: (data) => client.post('/admin/projects/assign/', data),
  getPendingSubmissions: () => client.get('/admin/submissions/pending/'),
  getEvaluationSummary: () => client.get('/admin/evaluations/summary/'),
};
