import React, { useEffect, useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { studentApi } from '../../api/student.api';

function toNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function extractChronologicalScores(snapshot, assignments) {
  const meta = snapshot?.metadata && typeof snapshot.metadata === 'object' ? snapshot.metadata : {};
  const candidateSeries = [
    meta.chronological_scores,
    meta.project_scores,
    meta.time_series,
    meta.score_history,
  ].find((arr) => Array.isArray(arr) && arr.length);

  if (Array.isArray(candidateSeries) && candidateSeries.length) {
    return candidateSeries
      .map((item) => (typeof item === 'object' && item !== null ? toNum(item.score ?? item.overall_score ?? item.value) : toNum(item)))
      .filter((n) => n != null)
      .slice(-5);
  }

  return assignments
    .filter((a) => a.status === 'COMPLETED' && toNum(a.latest_evaluation_score) != null)
    .sort((a, b) => new Date(a.completed_at || 0).getTime() - new Date(b.completed_at || 0).getTime())
    .map((a) => Number(a.latest_evaluation_score))
    .slice(-5);
}

export default function StudentGrowthDashboard() {
  const [snapshot, setSnapshot] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([studentApi.getProgressSnapshot(), studentApi.getAssignments()])
      .then(([progressRes, assignmentRes]) => {
        if (cancelled) return;
        const assignmentData = assignmentRes?.data;
        const list = Array.isArray(assignmentData) ? assignmentData : (assignmentData?.results || []);
        setSnapshot(progressRes?.data || null);
        setAssignments(list);
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || err?.message || 'Unable to load progress analytics.');
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const trajectoryScores = useMemo(() => extractChronologicalScores(snapshot, assignments), [snapshot, assignments]);
  const trajectoryData = useMemo(
    () => trajectoryScores.map((score, idx) => ({ project: `P${idx + 1}`, score })),
    [trajectoryScores],
  );
  const velocity = useMemo(() => {
    if (trajectoryScores.length < 2) return null;
    const first = trajectoryScores[0];
    const last = trajectoryScores[trajectoryScores.length - 1];
    if (!Number.isFinite(first) || first === 0 || !Number.isFinite(last)) return null;
    return ((last - first) / first) * 100;
  }, [trajectoryScores]);

  if (loading) {
    return (
      <div className="rounded-xl border border-teal-100 bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-600">Loading growth dashboard…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <section className="grid gap-5">
      <article className="rounded-2xl border border-teal-100 bg-white p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Trajectory</h3>
            <p className="text-sm text-slate-600">Score trend across your latest projects (up to 5).</p>
          </div>
          {velocity != null && velocity > 0 && (
            <span className="inline-flex rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
              Growth +{velocity.toFixed(1)}%
            </span>
          )}
        </div>
        <div className="h-64">
          {trajectoryData.length === 0 ? (
            <p className="pt-10 text-center text-sm text-slate-500">No scored project history available yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trajectoryData} margin={{ top: 16, right: 18, left: 4, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="project" stroke="#64748b" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} stroke="#64748b" tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#0d9488"
                  strokeWidth={3}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  isAnimationActive
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </article>
    </section>
  );
}
