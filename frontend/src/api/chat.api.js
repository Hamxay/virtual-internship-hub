import { client } from './client';

/**
 * Unwrap DRF paginated list when present.
 * @param {unknown} data
 * @returns {unknown[]}
 */
function listResults(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

/**
 * @returns {Promise<Array<{ id: number, created_at: string }>>}
 */
export async function getSessions() {
  const { data } = await client.get('/chat/sessions/');
  return listResults(data);
}

/**
 * @param {number} id
 * @returns {Promise<Array<{ id: number, role: string, content: string, timestamp: string }>>}
 */
export async function getSessionMessages(id) {
  const { data } = await client.get(`/chat/sessions/${id}/messages/`);
  return Array.isArray(data) ? data : listResults(data);
}

/**
 * @param {string} content
 * @param {number | null} [sessionId]
 * @returns {Promise<{ session_id: number, user_message: object, assistant_message: object }>}
 */
export async function sendMessage(content, sessionId = null) {
  const body = { content };
  if (sessionId != null) body.session_id = sessionId;
  const { data } = await client.post('/chat/message/', body);
  return data;
}
