import { client } from './client';

/**
 * @returns {Promise<Array>}
 */
export async function getNotifications() {
  const { data } = await client.get('notifications/');
  return Array.isArray(data) ? data : data?.results ?? [];
}

export async function markAsRead(id) {
  await client.post(`notifications/${id}/read/`);
}

export async function markAllAsRead() {
  await client.post('notifications/read-all/');
}
