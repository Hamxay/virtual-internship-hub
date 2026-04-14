import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ZAxis,
  Cell,
} from 'recharts';
import './AnalyticsCharts.css';

const CLUSTER_COLORS = {
  0: '#ef4444',
  1: '#eab308',
  2: '#22c55e',
};

function CustomScatterTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="analytics-charts-tooltip">
      <p className="analytics-charts-tooltip-title">{p.username}</p>
      <p className="analytics-charts-tooltip-meta">Cluster {p.cluster}</p>
      {p.xLabel && (
        <p className="analytics-charts-tooltip-meta">
          {p.xLabel}: {p.xRaw?.toFixed?.(1) ?? p.xRaw}
        </p>
      )}
      {p.yLabel && p.yLabel !== p.xLabel && (
        <p className="analytics-charts-tooltip-meta">
          {p.yLabel}: {p.yRaw?.toFixed?.(1) ?? p.yRaw}
        </p>
      )}
    </div>
  );
}

function clustersToScatterData(clusters) {
  if (!Array.isArray(clusters) || clusters.length === 0) return [];

  const domainKeys = [
    ...new Set(
      clusters.flatMap((row) =>
        Object.keys(row).filter((k) => k !== 'username' && k !== 'cluster')
      ),
    ),
  ].sort();

  const xKey = domainKeys[0] ?? 'score_x';
  const yKey = domainKeys[1] ?? domainKeys[0] ?? 'score_y';

  return clusters.map((row) => {
    const xRaw = Number(row[xKey]) || 0;
    const yRaw =
      domainKeys.length >= 2
        ? Number(row[yKey]) || 0
        : Math.max(0, Number(row.cluster) * 12 + xRaw * 0.15);

    return {
      username: row.username,
      cluster: Number(row.cluster) || 0,
      x: xRaw,
      y: yRaw,
      xRaw,
      yRaw,
      xLabel: xKey,
      yLabel: yKey,
      fill: CLUSTER_COLORS[Number(row.cluster)] ?? CLUSTER_COLORS[0],
    };
  });
}

function lineDataFromProgress(progress) {
  const series = progress?.time_series;
  if (!Array.isArray(series) || series.length === 0) {
    return [
      { stage: 'Baseline', score: 0 },
      { stage: 'Project 1', score: 0 },
      { stage: 'Project 2', score: 0 },
    ];
  }
  const labels = ['Baseline', 'Project 1', 'Project 2'];
  return labels.map((stage, i) => ({
    stage,
    score: Number(series[i]) || 0,
  }));
}

/**
 * @param {{ kpis?: object, clusters?: object[], progress?: object } | null} data
 */
export default function AnalyticsCharts({ data }) {
  const growth = data?.progress?.platform_average_growth ?? 0;
  const growthPositive = growth > 0;

  const scatterData = useMemo(() => clustersToScatterData(data?.clusters ?? []), [data?.clusters]);
  const lineData = useMemo(() => lineDataFromProgress(data?.progress), [data?.progress]);

  const kpis = data?.kpis ?? {};

  return (
    <div className="analytics-charts">
      <section className="analytics-charts-kpis">
        <article className="analytics-kpi-card">
          <h3>Total Students</h3>
          <p className="analytics-kpi-value">{kpis.total_students ?? '—'}</p>
        </article>
        <article className="analytics-kpi-card">
          <h3>Total Mentors</h3>
          <p className="analytics-kpi-value">{kpis.total_mentors ?? '—'}</p>
        </article>
        <article className="analytics-kpi-card">
          <h3>Total Projects</h3>
          <p className="analytics-kpi-value">{kpis.total_projects ?? '—'}</p>
        </article>
        <article className="analytics-kpi-card analytics-kpi-card-growth">
          <h3>Platform Avg. Growth</h3>
          <p
            className={`analytics-kpi-value analytics-kpi-growth ${
              growthPositive ? 'analytics-kpi-growth--positive' : ''
            }`}
          >
            {growth}%
          </p>
        </article>
      </section>

      <section className="analytics-charts-grid">
        <div className="analytics-chart-panel">
          <h2 className="analytics-chart-panel-title">Student Skill Clusters</h2>
          <p className="analytics-chart-panel-desc">K-Means clusters by domain scores (FR9).</p>
          <div className="analytics-chart-wrap">
            {scatterData.length === 0 ? (
              <p className="analytics-chart-empty">Not enough clustered student data yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <ScatterChart margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis type="number" dataKey="x" name="X" tick={{ fontSize: 12 }} stroke="#6b7280" />
                  <YAxis type="number" dataKey="y" name="Y" tick={{ fontSize: 12 }} stroke="#6b7280" />
                  <ZAxis range={[60, 60]} />
                  <Tooltip content={<CustomScatterTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                  <Scatter name="Students" data={scatterData} fill="#8884d8">
                    {scatterData.map((entry, i) => (
                      <Cell key={`cell-${entry.username}-${i}`} fill={entry.fill} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            )}
          </div>
          <ul className="analytics-cluster-legend">
            <li><span className="dot dot--0" /> Cluster 0</li>
            <li><span className="dot dot--1" /> Cluster 1</li>
            <li><span className="dot dot--2" /> Cluster 2</li>
          </ul>
        </div>

        <div className="analytics-chart-panel">
          <h2 className="analytics-chart-panel-title">Platform Skill Growth</h2>
          <p className="analytics-chart-panel-desc">Baseline vs. project stages (average).</p>
          <div className="analytics-chart-wrap">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={lineData} margin={{ top: 16, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="stage" tick={{ fontSize: 12 }} stroke="#6b7280" />
                <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" domain={[0, 'auto']} />
                <Tooltip
                  formatter={(v) => [`${v}`, 'Avg. score']}
                  labelStyle={{ color: '#111827' }}
                  contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb' }}
                />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 4, fill: '#2563eb' }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
    </div>
  );
}
