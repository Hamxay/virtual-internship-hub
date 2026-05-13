import React, { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import './AnalyticsCharts.css';

function round2(n) {
  return Math.round(n * 100) / 100;
}

/**
 * @param {object[]} rows
 * @returns {object[]}
 */
function buildPerformanceChartData(rows) {
  if (!rows.length) return [];

  const mapped = rows.map((r) => {
    const overall =
      r.overall_average != null && Number.isFinite(Number(r.overall_average))
        ? Number(r.overall_average)
        : null;
    const targets =
      r.chosen_domains_average != null && Number.isFinite(Number(r.chosen_domains_average))
        ? Number(r.chosen_domains_average)
        : null;
    return {
      student: r.username || `#${r.student_id ?? ''}`,
      overall,
      targets,
      hasScore: overall != null || targets != null,
    };
  });

  const anyScores = mapped.some((d) => d.hasScore);
  if (anyScores) {
    return mapped
      .filter((d) => d.hasScore)
      .sort((a, b) => (b.overall ?? b.targets ?? 0) - (a.overall ?? a.targets ?? 0));
  }

  return mapped.sort((a, b) => (a.student || '').localeCompare(b.student || ''));
}

function cohortStats(data) {
  const overalls = data.map((d) => d.overall).filter((v) => v != null);
  const targetAvgs = data.map((d) => d.targets).filter((v) => v != null);
  return {
    cohortOverall:
      overalls.length > 0 ? round2(overalls.reduce((s, v) => s + v, 0) / overalls.length) : null,
    cohortTargets:
      targetAvgs.length > 0 ? round2(targetAvgs.reduce((s, v) => s + v, 0) / targetAvgs.length) : null,
    nOverall: overalls.length,
    nTargets: targetAvgs.length,
  };
}

function PerformanceTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="analytics-charts-tooltip">
      <p className="analytics-charts-tooltip-title">{row.student}</p>
      {!row.hasScore && row.overall == null && row.targets == null ? (
        <p className="analytics-charts-tooltip-meta">No completed evaluations with scores yet.</p>
      ) : (
        <>
          {row.overall != null && (
            <p className="analytics-charts-tooltip-meta">Overall (all domains): {row.overall.toFixed(1)}</p>
          )}
          {row.targets != null && (
            <p className="analytics-charts-tooltip-meta">Target domains: {row.targets.toFixed(1)}</p>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Bar chart: each student’s average project performance (completed, evaluated work).
 * Uses explicit width/height (no ResponsiveContainer) so the chart always paints inside the admin flex layout.
 *
 * @param {{ studentRows: object[] }} props
 */
export default function StudentPerformanceOverviewChart({ studentRows = [] }) {
  const data = useMemo(() => buildPerformanceChartData(studentRows), [studentRows]);
  const stats = useMemo(() => cohortStats(data), [data]);
  const hasAnyBars = data.some((d) => d.overall != null || d.targets != null);

  const chartWidth = useMemo(() => {
    const perStudent = 56;
    const gutter = 160;
    const w = Math.max(480, data.length * perStudent + gutter);
    return Math.min(1280, w);
  }, [data.length]);

  if (studentRows.length === 0) {
    return (
      <section className="analytics-chart-panel student-performance-chart" aria-label="Student performance chart">
        <h3 className="analytics-chart-panel-title">Performance overview (chart)</h3>
        <p className="analytics-chart-panel-desc">No students match the current filter.</p>
        <p className="analytics-chart-empty">Adjust search or check that students exist on the platform.</p>
      </section>
    );
  }

  return (
    <section className="analytics-chart-panel student-performance-chart" aria-label="Student performance chart">
      <h3 className="analytics-chart-panel-title">Performance overview (chart)</h3>
      <p className="analytics-chart-panel-desc">
        Each bar uses the same averages as the table: <strong>Overall</strong> is the mean of all domains where the
        student has completed scored work; <strong>Target domains</strong> is limited to profile target domains.
        Reference line at 70.
        {hasAnyBars && stats.cohortOverall != null && (
          <>
            {' '}
            Cohort mean (overall): <strong>{stats.cohortOverall.toFixed(1)}</strong>
            {stats.nOverall > 0 ? ` · ${stats.nOverall} student${stats.nOverall === 1 ? '' : 's'}` : ''}
            {stats.cohortTargets != null && (
              <>
                {' '}
                · targets: <strong>{stats.cohortTargets.toFixed(1)}</strong>
              </>
            )}
          </>
        )}
        {!hasAnyBars && (
          <>
            {' '}
            <strong>No evaluation scores yet</strong> for these students—bars will appear after completed projects
            are scored.
          </>
        )}
      </p>

      <div className="analytics-chart-wrap student-performance-chart-scroll">
        <BarChart
          width={chartWidth}
          height={340}
          data={data}
          margin={{ top: 16, right: 16, left: 8, bottom: 72 }}
          barCategoryGap="16%"
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
          <XAxis
            dataKey="student"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            interval={0}
            angle={-35}
            textAnchor="end"
            height={78}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            width={40}
            label={{ value: 'Score', angle: -90, position: 'insideLeft', fill: '#9ca3af', fontSize: 11 }}
          />
          <Tooltip content={<PerformanceTooltip />} cursor={{ fill: 'rgba(37, 99, 235, 0.06)' }} />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 6 }} />
          <ReferenceLine
            y={70}
            stroke="#94a3b8"
            strokeDasharray="4 4"
            label={{ value: '70', fill: '#64748b', fontSize: 11 }}
          />
          <Bar dataKey="overall" name="Overall (all domains)" fill="#2563eb" radius={[4, 4, 0, 0]} maxBarSize={40} />
          <Bar dataKey="targets" name="Target domains only" fill="#7c3aed" radius={[4, 4, 0, 0]} maxBarSize={40} />
        </BarChart>
      </div>
    </section>
  );
}
