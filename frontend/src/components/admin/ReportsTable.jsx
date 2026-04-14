import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { downloadAuditCsv, fetchAuditCsvText } from '../../api/reports.api';
import './ReportsTable.css';

function parseCsvLine(line) {
  const out = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const c = line[i];
    if (c === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (c === ',' && !inQuotes) {
      out.push(cur);
      cur = '';
      continue;
    }
    cur += c;
  }
  out.push(cur);
  return out;
}

function parseAuditCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const header = parseCsvLine(lines[0]).map((h) => h.trim());
  const idx = (name) => header.findIndex((h) => h.toLowerCase() === name.toLowerCase());

  const iDate = idx('Date');
  const iStudent = idx('Student Username');
  const iProject = idx('Project Title');
  const iDomain = idx('Domain');
  const iScore = idx('AI Score');
  const iStatus = idx('Mentor Status');

  const rows = [];
  for (let r = 1; r < lines.length; r += 1) {
    const cells = parseCsvLine(lines[r]);
    rows.push({
      id: r,
      date: cells[iDate] ?? '',
      student: cells[iStudent] ?? '',
      project: cells[iProject] ?? '',
      domain: cells[iDomain] ?? '',
      score: cells[iScore] ?? '',
      status: cells[iStatus] ?? '',
    });
  }
  return rows;
}

export default function ReportsTable() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const text = await fetchAuditCsvText();
        if (!cancelled) setRows(parseAuditCsv(text));
      } catch (e) {
        if (!cancelled) setError(e?.message || 'Failed to load audit data.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => (r.student || '').toLowerCase().includes(q));
  }, [rows, search]);

  const handleExportCsv = useCallback(async () => {
    setExporting(true);
    setExportError('');
    try {
      const blob = await downloadAuditCsv();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'platform_audit.csv';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setExportError(e?.message || 'Export failed.');
    } finally {
      setExporting(false);
    }
  }, []);

  return (
    <div className="reports-table-root">
      <div className="reports-table-toolbar">
        <label className="reports-table-search">
          <span className="sr-only">Search Username</span>
          <input
            type="search"
            placeholder="Search username…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          className="reports-table-export-btn"
          onClick={handleExportCsv}
          disabled={exporting}
        >
          {exporting ? 'Exporting…' : 'Export CSV Report'}
        </button>
      </div>

      {error && <p className="reports-table-error">{error}</p>}
      {exportError && <p className="reports-table-error">{exportError}</p>}

      {loading ? (
        <div className="reports-table-loading">
          <span className="reports-table-spinner" aria-hidden />
          <p>Loading audit rows…</p>
        </div>
      ) : (
        <div className="reports-table-scroll">
          <table className="reports-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Student</th>
                <th>Project</th>
                <th>Domain</th>
                <th>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="reports-table-empty">
                    {rows.length === 0
                      ? 'No audit rows returned yet.'
                      : 'No rows match your search.'}
                  </td>
                </tr>
              ) : (
                filtered.map((r) => (
                  <tr key={r.id}>
                    <td>{r.date}</td>
                    <td>{r.student}</td>
                    <td>{r.project}</td>
                    <td>{r.domain}</td>
                    <td>{r.score}</td>
                    <td>
                      <span className="reports-table-status">{r.status}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
