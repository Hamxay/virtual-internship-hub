import React, { useEffect, useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { getAdminAnalytics } from '../../api/reports.api';
import '../../components/admin/AnalyticsCharts.css';
import './StudentAnalytics.css';

function rosterInDomain(students, domainName) {
  if (!domainName || !Array.isArray(students)) return [];
  return students
    .map((s) => ({
      username: s.username,
      student_id: s.student_id,
      score: s[domainName],
    }))
    .filter((r) => r.score != null && Number.isFinite(Number(r.score)))
    .map((r) => ({
      username: r.username,
      student_id: r.student_id,
      score: Number(r.score),
    }));
}

function curriculumKpisForDomain(students, domainName) {
  const roster = rosterInDomain(students, domainName);
  const n = roster.length;
  if (n === 0) {
    return { enrolled: 0, domainAvg: null, passRate: null };
  }
  const scores = roster.map((r) => r.score);
  const domainAvg = Math.round((scores.reduce((a, b) => a + b, 0) / n) * 100) / 100;
  const pass = scores.filter((s) => s >= 60).length;
  const passRate = Math.round((100 * pass) / n * 10) / 10;
  return { enrolled: n, domainAvg, passRate };
}

function DomainBarTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="analytics-charts-tooltip">
      <p className="analytics-charts-tooltip-title">{row.username}</p>
      <p className="analytics-charts-tooltip-meta">Score: {row.score}</p>
    </div>
  );
}

/**
 * Curriculum Health — macro view: one official domain at a time, KPIs, distribution bar chart, roster.
 */
export default function CurriculumHealth() {
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
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
        setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
        setAnalyticsData(null);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const students = useMemo(() => analyticsData?.students ?? [], [analyticsData]);
  const officialDomains = useMemo(() => analyticsData?.official_domains ?? [], [analyticsData]);

  useEffect(() => {
    if (!officialDomains.length) return;
    setSelectedDomain((prev) => {
      if (prev && officialDomains.includes(prev)) return prev;
      const firstWithData = officialDomains.find((d) =>
        students.some((s) => s[d] != null && Number.isFinite(Number(s[d]))),
      );
      return firstWithData ?? officialDomains[0];
    });
  }, [officialDomains, students]);

  const kpis = useMemo(
    () => curriculumKpisForDomain(students, selectedDomain),
    [students, selectedDomain],
  );

  const barData = useMemo(() => rosterInDomain(students, selectedDomain), [students, selectedDomain]);

  return (
    <div className="admin-command-center">
      <header className="admin-command-center-header">
        <h1>Curriculum Health</h1>
        <p>Macro analytics by official catalog domain: enrollment, averages, pass rate, and score distribution.</p>
      </header>

      <div className="admin-command-center-body">
        {loading && (
          <div className="admin-command-center-loading">
            <span className="admin-command-center-spinner" aria-hidden />
            <p>Loading curriculum metrics…</p>
          </div>
        )}

        {!loading && error && (
          <div className="admin-command-center-error" role="alert">
            {error}
          </div>
        )}

        {!loading && !error && officialDomains.length > 0 && (
          <div className="analytics-charts command-center-curriculum">
            <div className="command-center-domain-select mb-4">
              <label htmlFor="curriculum-domain-select" className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
                Select domain
              </label>
              <select
                id="curriculum-domain-select"
                className="mt-1 block w-full max-w-md rounded-md border border-gray-300 bg-white py-2 pl-3 pr-8 text-sm text-gray-900 shadow-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                value={selectedDomain}
                onChange={(e) => setSelectedDomain(e.target.value)}
              >
                {officialDomains.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>

            <section className="analytics-charts-kpis mb-6">
              <div className="analytics-charts-kpi-cards">
                <article className="analytics-kpi-card">
                  <h3>Total Students Enrolled</h3>
                  <p className="analytics-kpi-value">{kpis.enrolled}</p>
                </article>
                <article className="analytics-kpi-card">
                  <h3>Domain Average Score</h3>
                  <p className="analytics-kpi-value">{kpis.domainAvg != null ? kpis.domainAvg : '—'}</p>
                </article>
                <article className="analytics-kpi-card">
                  <h3>Pass Rate (≥ 60)</h3>
                  <p className="analytics-kpi-value">
                    {kpis.passRate != null ? `${kpis.passRate}%` : '—'}
                  </p>
                </article>
              </div>
            </section>

            <div className="analytics-chart-panel mb-6">
              <h2 className="analytics-chart-panel-title">Score distribution — {selectedDomain}</h2>
              <p className="analytics-chart-panel-desc">One bar per student with a recorded score in this domain.</p>
              <div className="analytics-chart-wrap">
                {barData.length === 0 ? (
                  <p className="analytics-chart-empty">No completed scores in this domain yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={380}>
                    <BarChart data={barData} margin={{ top: 16, right: 16, left: 8, bottom: 64 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="username"
                        tick={{ fontSize: 10 }}
                        stroke="#6b7280"
                        angle={-32}
                        textAnchor="end"
                        height={72}
                        interval={0}
                      />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} stroke="#6b7280" />
                      <Tooltip content={<DomainBarTooltip />} cursor={{ fill: 'rgba(139, 92, 246, 0.08)' }} />
                      <ReferenceLine
                        y={60}
                        stroke="#dc2626"
                        strokeDasharray="3 3"
                        label={{ value: 'Passing Baseline', position: 'insideTopRight', fill: '#dc2626', fontSize: 12 }}
                      />
                      <Bar dataKey="score" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            <div className="analytics-chart-panel">
              <h2 className="analytics-chart-panel-title">Roster — {selectedDomain}</h2>
              <p className="analytics-chart-panel-desc">Students with at least one completed score in this domain.</p>
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-gray-50 text-gray-700">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Student</th>
                      <th className="px-3 py-2 font-semibold">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {barData.length === 0 ? (
                      <tr>
                        <td colSpan={2} className="px-3 py-6 text-center text-gray-500">
                          No students in this domain.
                        </td>
                      </tr>
                    ) : (
                      barData.map((r) => (
                        <tr key={r.student_id ?? r.username} className="border-t border-gray-100">
                          <td className="px-3 py-2 text-gray-900">{r.username}</td>
                          <td className="px-3 py-2 text-gray-800">{r.score}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {!loading && !error && officialDomains.length === 0 && (
          <p className="analytics-chart-empty">No official domains configured in the catalog.</p>
        )}
      </div>
    </div>
  );
}
