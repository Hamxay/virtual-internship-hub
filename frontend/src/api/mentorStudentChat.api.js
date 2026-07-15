import { client } from './client';

export const mentorStudentChatApi = {
  getEligibleMentors: () => client.get('/chat/mentor/eligible-mentors/'),
  getEligibleStudents: () => client.get('/chat/mentor/eligible-students/'),
  startConversation: (payload) => client.post('/chat/mentor/conversations/start/', payload),
  getConversations: () => client.get('/chat/mentor/conversations/'),
  getMessages: (conversationId) => client.get(`/chat/mentor/conversations/${conversationId}/messages/`),
  sendMessage: (conversationId, content) => client.post(`/chat/mentor/conversations/${conversationId}/messages/`, { content }),
};
