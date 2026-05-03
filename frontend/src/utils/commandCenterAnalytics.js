/**
 * Command Center analytics — shared helpers for domain-centric admin views.
 * Meta keys on each student row from GET admin/reports/analytics/.
 */
export const STUDENT_ROW_META_KEYS = new Set(['username', 'student_id', 'overall_average']);

/**
 * Domain columns that should appear for the current filtered rows (sparse-aware).
 * @param {object[]} filteredRows
 * @param {string[]} [domainOrder] preferred column order (e.g. official_domains from API)
 * @returns {string[]}
 */
export function getVisibleDomainColumns(filteredRows, domainOrder = []) {
  const withData = new Set();
  for (const row of filteredRows) {
    if (!row || typeof row !== 'object') continue;
    Object.keys(row).forEach((key) => {
      if (STUDENT_ROW_META_KEYS.has(key)) return;
      const v = row[key];
      if (v != null && typeof v === 'number' && Number.isFinite(v)) {
        withData.add(key);
      }
    });
  }
  const ordered = domainOrder.filter((d) => withData.has(d));
  const rest = [...withData].filter((d) => !ordered.includes(d)).sort((a, b) => a.localeCompare(b));
  return [...ordered, ...rest];
}

/**
 * Tailwind cell classes for numeric score heatmap.
 * @param {number|null|undefined} score
 * @returns {string}
 */
export function scoreHeatmapCellClass(score) {
  if (score == null || !Number.isFinite(Number(score))) {
    return 'bg-gray-50 text-gray-500';
  }
  const n = Number(score);
  if (n >= 80) return 'bg-green-100 text-green-700 font-medium';
  if (n >= 60) return 'bg-yellow-100 text-yellow-700 font-medium';
  return 'bg-red-100 text-red-700 font-medium';
}

export function escapeCsvCell(value) {
  const s = value === null || value === undefined ? '' : String(value);
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/**
 * Build CSV text from filtered student rows and visible domain columns.
 * @param {object[]} rows
 * @param {string[]} domainColumns
 * @returns {string}
 */
export function buildStudentMatrixCsv(rows, domainColumns) {
  const headers = ['Student Name', ...domainColumns, 'Overall Average'];
  const lines = [headers.map(escapeCsvCell).join(',')];
  for (const row of rows) {
    const cells = [
      row.username ?? '',
      ...domainColumns.map((d) => {
        const v = row[d];
        return v == null ? '' : String(v);
      }),
      row.overall_average == null ? '' : String(row.overall_average),
    ];
    lines.push(cells.map(escapeCsvCell).join(','));
  }
  return lines.join('\n');
}

export function triggerCsvDownload(csvText, filename) {
  const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export function filterStudentRowsBySearch(rows, searchQuery) {
  const q = (searchQuery || '').trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((r) => (r.username || '').toLowerCase().includes(q));
}
