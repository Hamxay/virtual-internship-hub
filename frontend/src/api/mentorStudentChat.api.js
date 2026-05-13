import { client } from './client';

export const mentorStudentChatApi = {
  getEligibleMentors: () => client.get('/chat/mentor/eligible-mentors/'),
  startConversation: (mentorId) => client.post('/chat/mentor/conversations/start/', { mentor_id: mentorId }),
  getConversations: () => client.get('/chat/mentor/conversations/'),
  getMessages: (conversationId) => client.get(`/chat/mentor/conversations/${conversationId}/messages/`),
  sendMessage: (conversationId, content) => client.post(`/chat/mentor/conversations/${conversationId}/messages/`, { content }),
};
