import { client } from './client';

const ADMIN_REPORTS_BASE = 'admin/reports';

/**
 * FR9 admin analytics (KPIs and official-domain student matrix).
 * @returns {Promise<import('axios').AxiosResponse['data']>}
 */
export async function getAdminAnalytics() {
  const { data } = await client.get(`${ADMIN_REPORTS_BASE}/analytics/`);
  return data;
}

/**
 * FR8 audit CSV — binary download (blob).
 * @returns {Promise<Blob>}
 */
export async function downloadAuditCsv() {
  const { data } = await client.get(`${ADMIN_REPORTS_BASE}/export/`, {
    responseType: 'blob',
  });
  return data;
}

/**
 * Same export as plain text for populating the audit table (not for file download).
 * @returns {Promise<string>}
 */
export async function fetchAuditCsvText() {
  const { data } = await client.get(`${ADMIN_REPORTS_BASE}/export/`, {
    responseType: 'text',
  });
  return data;
}
