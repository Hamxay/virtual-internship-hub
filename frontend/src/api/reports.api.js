import { client } from './client';

const ADMIN_REPORTS_BASE = 'admin/reports';

/** Admin analytics payload (KPIs + student × domain matrix). */
export async function getAdminAnalytics() {
  const { data } = await client.get(`${ADMIN_REPORTS_BASE}/analytics/`);
  return data;
}

/** Audit export as ``Blob`` (file download). */
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
