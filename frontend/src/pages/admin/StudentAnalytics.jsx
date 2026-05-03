import React, { useCallback, useMemo, useState } from 'react';
import { getAdminAnalytics } from '../../api/reports.api';
import AnalyticsCharts from '../../components/admin/AnalyticsCharts';
import StudentDomainHeatmapTable from '../../components/admin/StudentDomainHeatmapTable';
import {
  buildStudentMatrixCsv,
  filterStudentRowsBySearch,
  getVisibleDomainColumns,
  triggerCsvDownload,
} from '../../utils/commandCenterAnalytics';
import './StudentAnalytics.css';

/**
 * Student Analytics — platform KPIs, domain heatmap (smart sparse columns), FR8 matrix CSV export.
 */
export default function StudentAnalytics() {
  const [studentSearch, setStudentSearch] = useState('');
  const [analyticsData, setAnalyticsData] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  const [analyticsError, setAnalyticsError] = useState('');
  const [exporting, setExporting] = useState(false);

  React.useEffect(() => {
    let cancelled = false;
    setAnalyticsLoading(true);
    setAnalyticsError('');
    getAdminAnalytics()
      .then((data) => {
        if (cancelled) return;
        setAnalyticsData(data);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err?.response?.data?.detail ||
          err?.message ||
          'Unable to load analytics. Ensure you are logged in as an admin with API access.';
        setAnalyticsError(typeof msg === 'string' ? msg : JSON.stringify(msg));
        setAnalyticsData(null);
      })
      .finally(() => {
        if (cancelled) return;
        setAnalyticsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const students = useMemo(() => analyticsData?.students ?? [], [analyticsData]);
  const officialDomains = useMemo(() => analyticsData?.official_domains ?? [], [analyticsData]);

  const filteredRows = useMemo(
    () => filterStudentRowsBySearch(students, studentSearch),
    [students, studentSearch],
  );

  const visibleDomainColumns = useMemo(
    () => getVisibleDomainColumns(filteredRows, officialDomains),
    [filteredRows, officialDomains],
  );

  const handleExportMatrixCsv = useCallback(() => {
    setExporting(true);
    try {
      const csv = buildStudentMatrixCsv(filteredRows, visibleDomainColumns);
      const stamp = new Date().toISOString().slice(0, 10);
      triggerCsvDownload(csv, `student_domain_matrix_${stamp}.csv`);
    } finally {
      setExporting(false);
    }
  }, [filteredRows, visibleDomainColumns]);

  return (
    <div className="admin-command-center">
      <header className="admin-command-center-header">
        <h1>Student Analytics & Compliance Audit</h1>
        <p>
          Domain-centric score matrix with heatmap styling. Export CSV matches the filtered table (FR8 raw
          audit for the visible cohort).
        </p>
      </header>

      <div className="admin-command-center-body">
        {analyticsLoading && (
          <div className="admin-command-center-loading">
            <span className="admin-command-center-spinner" aria-hidden />
            <p>Loading analytics…</p>
          </div>
        )}

        {!analyticsLoading && analyticsError && (
          <div className="admin-command-center-error" role="alert">
            {analyticsError}
          </div>
        )}

        {!analyticsLoading && analyticsData && (
          <div className="admin-command-center-split command-center-student-stack">
            <AnalyticsCharts kpis={analyticsData.kpis ?? {}} />

            <section className="command-center-heatmap-section" aria-label="Student domain matrix">
              <div className="command-center-heatmap-toolbar">
                <h2 className="admin-command-center-audit-title">Student domain performance</h2>
                <div className="command-center-heatmap-actions">
                  <label htmlFor="student-matrix-search" className="sr-only">
                    Filter by student name
                  </label>
                  <input
                    id="student-matrix-search"
                    type="search"
                    placeholder="Search student name…"
                    value={studentSearch}
                    onChange={(e) => setStudentSearch(e.target.value)}
                    className="block w-full min-w-[12rem] max-w-xs rounded-md border border-gray-300 bg-white py-2 pl-3 pr-3 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    className="command-center-export-csv-btn shrink-0"
                    onClick={handleExportMatrixCsv}
                    disabled={exporting || filteredRows.length === 0}
                  >
                    {exporting ? 'Exporting…' : 'Export to CSV'}
                  </button>
                </div>
              </div>
              <p className="command-center-heatmap-hint text-sm text-gray-500">
                Columns appear only when at least one visible student has a score in that domain. Empty cells are
                not enrolled or no completed score in that domain.
              </p>
              <StudentDomainHeatmapTable rows={filteredRows} domainColumns={visibleDomainColumns} />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
