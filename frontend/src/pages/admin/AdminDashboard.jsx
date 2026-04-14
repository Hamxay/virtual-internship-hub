import React, { useEffect, useState } from 'react';
import { getAdminAnalytics } from '../../api/reports.api';
import AnalyticsCharts from '../../components/admin/AnalyticsCharts';
import ReportsTable from '../../components/admin/ReportsTable';
import './AdminDashboard.css';

/**
 * Admin Command Center — FR9 charts vs FR8 audit table (embedded in main admin shell).
 */
export default function AdminDashboard() {
  const [activeView, setActiveView] = useState('charts');
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await getAdminAnalytics();
        if (!cancelled) setAnalyticsData(data);
      } catch (e) {
        const msg =
          e?.response?.data?.detail ||
          e?.message ||
          'Unable to load analytics. Ensure you are logged in as an admin with API access.';
        if (!cancelled) setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="admin-command-center">
      <header className="admin-command-center-header">
        <h1>Admin Command Center</h1>
        <p>Visual intelligence and compliance exports in one place.</p>
      </header>

      <div className="admin-command-center-toggle" role="tablist" aria-label="Report mode">
        <button
          type="button"
          role="tab"
          aria-selected={activeView === 'charts'}
          className={activeView === 'charts' ? 'is-active' : ''}
          onClick={() => setActiveView('charts')}
        >
          Visual Intelligence (FR9)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeView === 'table'}
          className={activeView === 'table' ? 'is-active' : ''}
          onClick={() => setActiveView('table')}
        >
          Compliance Audit (FR8)
        </button>
      </div>

      <div className="admin-command-center-body">
        {activeView === 'charts' && loading && (
          <div className="admin-command-center-loading">
            <span className="admin-command-center-spinner" aria-hidden />
            <p>Loading analytics…</p>
          </div>
        )}

        {activeView === 'charts' && error && !loading && (
          <div className="admin-command-center-error" role="alert">
            {error}
          </div>
        )}

        {activeView === 'charts' && !loading && !error && (
          <AnalyticsCharts data={analyticsData} />
        )}

        {activeView === 'table' && <ReportsTable />}
      </div>
    </div>
  );
}
