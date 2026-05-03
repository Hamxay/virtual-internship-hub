import React from 'react';
import './AnalyticsCharts.css';

/**
 * Platform KPI cards for admin analytics (FR9 headline metrics).
 *
 * @param {{ kpis?: object }} props
 */
export default function AnalyticsCharts({ kpis = {} }) {
  return (
    <div className="analytics-charts">
      <section className="analytics-charts-kpis">
        <div className="analytics-charts-kpi-cards">
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
        </div>
      </section>
    </div>
  );
}
