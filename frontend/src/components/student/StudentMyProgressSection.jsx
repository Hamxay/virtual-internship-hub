import React, { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { studentApi } from '../../api/student.api';
import { AwardIcon, BarChartIcon, TargetIcon } from '../ui/Icons';

function normalizeAssignments(res) {
  const data = res?.data;
  return Array.isArray(data) ? data : (data?.results || []);
}

function toFiniteScore(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function buildDomainMetrics(assignments) {
  const completed = assignments.filter(
    (a) => a.status === 'COMPLETED' && toFiniteScore(a.latest_evaluation_score) != null,
  );

  const byDomain = new Map();
  for (const a of completed) {
    const name = a.project_template?.domain?.name || 'Other';
    const score = toFiniteScore(a.latest_evaluation_score);
    if (!byDomain.has(name)) byDomain.set(name, []);
    byDomain.get(name).push(score);
  }

  const domainRows = [...byDomain.entries()]
    .map(([domain, scores]) => {
      const sum = scores.reduce((s, x) => s + x, 0);
      return {
        domain,
        avgScore: sum / scores.length,
        projectCount: scores.length,
      };
    })
    .sort((x, y) => y.avgScore - x.avgScore);

  const allScores = completed.map((a) => toFiniteScore(a.latest_evaluation_score));
  const overallAvg = allScores.length
    ? allScores.reduce((s, x) => s + x, 0) / allScores.length
    : null;
  const totalPointsAcrossDomains = allScores.reduce((s, x) => s + x, 0);

  return {
    completedCount: completed.length,
    domainRows,
    overallAvg,
    totalPointsAcrossDomains,
  };
}

function DomainAvgTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="font-semibold text-slate-900">{row.domain}</div>
      <div className="mt-1 text-slate-600">
        Average: <span className="font-medium text-slate-800">{row.avgScore.toFixed(1)}%</span>
      </div>
      <div className="text-slate-600">
        Projects: <span className="font-medium text-slate-800">{row.projectCount}</span>
      </div>
    </div>
  );
}

function CountTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="font-semibold text-slate-900">{row.domain}</div>
      <div className="mt-1 text-slate-600">
        Completed: <span className="font-medium text-slate-800">{row.projectCount}</span>
      </div>
    </div>
  );
}

export default function StudentMyProgressSection() {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    studentApi
      .getAssignments()
      .then((res) => {
        if (cancelled) return;
        setAssignments(normalizeAssignments(res));
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || err?.message || 'Unable to load your progress.');
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const metrics = useMemo(() => buildDomainMetrics(assignments), [assignments]);

  if (loading) {
    return (
      <div className="dashboard-section">
        <h1>My Progress</h1>
        <p className="section-desc">Charts and stats from your completed, scored projects.</p>
        <div className="info-card">
          <p>Loading progress…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-section">
        <h1>My Progress</h1>
        <p className="section-desc">Charts and stats from your completed, scored projects.</p>
        <div className="info-card" style={{ borderColor: '#fecaca', background: '#fef2f2' }}>
          <p style={{ color: '#991b1b', margin: 0 }}>{error}</p>
        </div>
      </div>
    );
  }

  const hasData = metrics.domainRows.length > 0;

  return (
    <div className="dashboard-section">
      <h1>My Progress</h1>
      <p className="section-desc">
        See how many projects you&apos;ve completed, your average score in each domain, and your combined score
        across all completed work (evaluation scores are 0–100%).
      </p>

      <div
        className="progress-cards-grid"
        style={{ marginBottom: '1.5rem' }}
      >
        <div className="progress-card">
          <div className="progress-icon" style={{ background: '#ccfbf1', color: '#0f766e' }}>
            <TargetIcon className="w-6 h-6" />
          </div>
          <div>
            <div className="progress-value">{metrics.completedCount}</div>
            <div className="progress-label">Projects completed</div>
          </div>
        </div>
        <div className="progress-card">
          <div className="progress-icon" style={{ background: '#e0e7ff', color: '#4338ca' }}>
            <BarChartIcon className="w-6 h-6" />
          </div>
          <div>
            <div className="progress-value">
              {metrics.overallAvg != null ? `${metrics.overallAvg.toFixed(1)}%` : '—'}
            </div>
            <div className="progress-label">Overall average</div>
          </div>
        </div>
        <div className="progress-card">
          <div className="progress-icon" style={{ background: '#fef3c7', color: '#b45309' }}>
            <AwardIcon className="w-6 h-6" />
          </div>
          <div>
            <div className="progress-value">
              {metrics.totalPointsAcrossDomains > 0
                ? Math.round(metrics.totalPointsAcrossDomains)
                : '—'}
            </div>
            <div className="progress-label">Total points (sum)</div>
          </div>
        </div>
      </div>

      {!hasData ? (
        <div className="info-card">
          <p style={{ margin: 0, textAlign: 'center', color: '#64748b' }}>
            Complete and submit a project to get an evaluation score. Your domain breakdown and charts will appear
            here.
          </p>
        </div>
      ) : (
        <div className="grid gap-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          <article className="rounded-2xl border border-teal-100 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900" style={{ margin: '0 0 0.25rem 0' }}>
              Average score by domain
            </h3>
            <p className="text-sm text-slate-600" style={{ margin: '0 0 1rem 0' }}>
              Mean evaluation score for each domain you&apos;ve finished.
            </p>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={metrics.domainRows}
                  margin={{ top: 8, right: 8, left: 0, bottom: 48 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="domain"
                    tick={{ fontSize: 11, fill: '#64748b' }}
                    interval={0}
                    angle={-22}
                    textAnchor="end"
                    height={52}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 11, fill: '#64748b' }}
                    tickFormatter={(v) => `${v}%`}
                    width={40}
                  />
                  <Tooltip content={<DomainAvgTooltip />} cursor={{ fill: 'rgba(15, 118, 110, 0.06)' }} />
                  <Bar dataKey="avgScore" fill="#0d9488" name="Average %" radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article className="rounded-2xl border border-teal-100 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900" style={{ margin: '0 0 0.25rem 0' }}>
              Projects per domain
            </h3>
            <p className="text-sm text-slate-600" style={{ margin: '0 0 1rem 0' }}>
              How many scored, completed projects you have in each domain.
            </p>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={metrics.domainRows}
                  margin={{ top: 8, right: 8, left: 0, bottom: 48 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="domain"
                    tick={{ fontSize: 11, fill: '#64748b' }}
                    interval={0}
                    angle={-22}
                    textAnchor="end"
                    height={52}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} width={32} />
                  <Tooltip content={<CountTooltip />} cursor={{ fill: 'rgba(67, 56, 202, 0.06)' }} />
                  <Bar dataKey="projectCount" fill="#6366f1" name="Projects" radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>
        </div>
      )}
    </div>
  );
}
