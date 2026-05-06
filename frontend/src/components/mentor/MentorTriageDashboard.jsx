import React, { useMemo, useState } from 'react';

const FILTER = {
  ALL: 'all',
  NEEDS_INTERVENTION: 'needs_intervention',
  TOP_GROWERS: 'top_growers',
};

function studentDisplayName(row) {
  const fn = (row.first_name || '').trim();
  const ln = (row.last_name || '').trim();
  const full = `${fn} ${ln}`.trim();
  return full || row.username || '—';
}

function parseVelocity(row) {
  const raw = row?.skill_insights?.velocity_score;
  if (typeof raw !== 'string') return null;
  const parsed = Number(raw.replace('%', '').trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function progressSummary(row) {
  const trend = row?.skill_insights?.trend_direction;
  const velocity = parseVelocity(row);
  if (trend === 'DOWN') return 'Falling';
  if (trend === 'UP' && velocity != null && velocity >= 5) return 'Rising fast';
  if (trend === 'UP') return 'Improving';
  if (trend === 'STABLE' && velocity != null && Math.abs(velocity) < 1) return 'Steady';
  return 'No clear trend yet';
}

function triageRank(row) {
  const trend = row?.skill_insights?.trend_direction;
  if (trend === 'DOWN') return 0;
  if (trend === 'STABLE') return 1;
  if (trend === 'UP') return 2;
  return 3;
}

export default function MentorTriageDashboard({ students = [], loading }) {
  const [activeFilter, setActiveFilter] = useState(FILTER.ALL);

  const sortedStudents = useMemo(() => {
    return [...students].sort((a, b) => {
      const rankDiff = triageRank(a) - triageRank(b);
      if (rankDiff !== 0) return rankDiff;

      const av = parseVelocity(a);
      const bv = parseVelocity(b);
      if (av == null && bv == null) return studentDisplayName(a).localeCompare(studentDisplayName(b));
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av !== bv) return av - bv;
      return studentDisplayName(a).localeCompare(studentDisplayName(b));
    });
  }, [students]);

  const visibleStudents = useMemo(() => {
    if (activeFilter === FILTER.NEEDS_INTERVENTION) {
      return sortedStudents.filter((s) => s?.skill_insights?.trend_direction === 'DOWN');
    }
    if (activeFilter === FILTER.TOP_GROWERS) {
      return sortedStudents.filter((s) => s?.skill_insights?.trend_direction === 'UP');
    }
    return sortedStudents;
  }, [activeFilter, sortedStudents]);

  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-slate-200 bg-white py-16 text-slate-500">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600" aria-hidden />
        <span className="ml-3 text-sm font-medium">Loading students…</span>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="inline-flex rounded-xl bg-slate-100 p-1 ring-1 ring-slate-200">
        <button
          type="button"
          onClick={() => setActiveFilter(FILTER.ALL)}
          className={`rounded-md px-3 py-1.5 text-sm font-semibold transition ${
            activeFilter === FILTER.ALL
              ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          All
        </button>
        <button
          type="button"
          onClick={() => setActiveFilter(FILTER.NEEDS_INTERVENTION)}
          className={`rounded-md px-3 py-1.5 text-sm font-semibold transition ${
            activeFilter === FILTER.NEEDS_INTERVENTION
              ? 'bg-red-50 text-red-700 shadow-sm ring-1 ring-red-200'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Needs help
        </button>
        <button
          type="button"
          onClick={() => setActiveFilter(FILTER.TOP_GROWERS)}
          className={`rounded-md px-3 py-1.5 text-sm font-semibold transition ${
            activeFilter === FILTER.TOP_GROWERS
              ? 'bg-emerald-50 text-emerald-700 shadow-sm ring-1 ring-emerald-200'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Improving most
        </button>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">Students in your coaching list</p>
        <span className="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white">
          {visibleStudents.length}
        </span>
      </div>

      {visibleStudents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/80 px-6 py-14 text-center text-sm text-slate-600">
          No students found for this triage filter.
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {visibleStudents.map((student, idx) => {
            const trend = student?.skill_insights?.trend_direction;
            const advice = student?.skill_insights?.actionable_advice || 'No coaching advice available yet.';
            const velocity = parseVelocity(student);
            const summary = progressSummary(student);
            const isDown = trend === 'DOWN';
            const isUp = trend === 'UP';
            const cardKey = `${student?.student_id ?? student?.username ?? idx}-${idx}`;

            return (
              <article
                key={cardKey}
                className={`rounded-xl border p-5 shadow-sm ${
                  isDown
                    ? 'border-l-4 border-red-500 bg-red-50'
                    : isUp
                      ? 'border-l-4 border-emerald-500 bg-emerald-50'
                      : 'border-slate-200 bg-white'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-slate-900">{studentDisplayName(student)}</h3>
                    <p className="mt-1 text-sm text-slate-600">
                      Current score:{' '}
                      <span className="font-semibold text-slate-800">
                        {student.domain_average != null ? student.domain_average : '—'}
                      </span>
                    </p>
                    <p className="mt-0.5 text-sm text-slate-500">{summary}</p>
                  </div>
                  <div className="text-right">
                    <p
                      className={`text-base font-semibold ${
                        velocity == null ? 'text-slate-500' : velocity < 0 ? 'text-red-700' : 'text-emerald-700'
                      }`}
                    >
                      {velocity == null ? '—' : `${velocity >= 0 ? '+' : ''}${velocity.toFixed(1)}%`}
                    </p>
                    <p className="mt-0.5 text-sm text-slate-600">Recent progress</p>
                  </div>
                </div>
                <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Actionable advice</p>
                  <p className="mt-1 text-sm leading-relaxed text-slate-700">{advice}</p>
                </div>
                <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-sm italic text-slate-500">
                  {student.latest_feedback_summary || 'No recent evaluator feedback in this domain yet.'}
                </p>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
