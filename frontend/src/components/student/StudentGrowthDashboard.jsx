import React, { useEffect, useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
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

function extractRadarData(assignments) {
  const completed = assignments.filter((a) => a.status === 'COMPLETED');
  const metrics = {
    correctness: [],
    design: [],
    originality: [],
    grammar: [],
  };

  completed.forEach((assignment) => {
    const latestEval = assignment?.latest_submission?.evaluations?.[0];
    if (!latestEval) return;
    const correctness = toNum(latestEval.correctness_score);
    const design = toNum(latestEval.design_quality_score);
    const originality = toNum(latestEval.originality_score);
    const grammar = toNum(latestEval.grammar_score);
    if (correctness != null) metrics.correctness.push(correctness);
    if (design != null) metrics.design.push(design);
    if (originality != null) metrics.originality.push(originality);
    if (grammar != null) metrics.grammar.push(grammar);
  });

  const avg = (list) => (list.length ? Math.round((list.reduce((a, b) => a + b, 0) / list.length) * 10) / 10 : null);
  return [
    { skill: 'Correctness', score: avg(metrics.correctness) },
    { skill: 'Design', score: avg(metrics.design) },
    { skill: 'Originality', score: avg(metrics.originality) },
    { skill: 'Grammar', score: avg(metrics.grammar) },
  ].filter((x) => x.score != null);
}

function buildDomainWeakness(assignments) {
  const buckets = {};
  assignments
    .filter((a) => a.status === 'COMPLETED' && toNum(a.latest_evaluation_score) != null)
    .forEach((a) => {
      const name = a?.project_template?.domain?.name;
      if (!name) return;
      if (!buckets[name]) buckets[name] = [];
      buckets[name].push(Number(a.latest_evaluation_score));
    });
  const ranked = Object.entries(buckets)
    .map(([name, vals]) => ({
      name,
      avg: vals.reduce((acc, cur) => acc + cur, 0) / vals.length,
    }))
    .sort((a, b) => a.avg - b.avg);
  return ranked[0] || null;
}

function suggestionForSkill(skillName) {
  if (skillName === 'Design') {
    return "Your Design scores are lagging. We recommend the 'Responsive CSS' project template next.";
  }
  if (skillName === 'Correctness') {
    return "Your Correctness scores dipped. We recommend a debugging-focused project with strict test cases.";
  }
  if (skillName === 'Originality') {
    return "Originality is your lowest axis. Try a project requiring custom problem framing and unique implementation.";
  }
  return "Grammar and clarity are trailing. Choose a project with documentation milestones and feedback checkpoints.";
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

  const radarData = useMemo(() => extractRadarData(assignments), [assignments]);
  const lowestSkill = useMemo(() => {
    if (!radarData.length) return null;
    return [...radarData].sort((a, b) => a.score - b.score)[0];
  }, [radarData]);
  const weakestDomain = useMemo(() => buildDomainWeakness(assignments), [assignments]);

  const recommendationText = useMemo(() => {
    if (lowestSkill) return suggestionForSkill(lowestSkill.skill);
    if (weakestDomain) {
      return `Your ${weakestDomain.name} scores dropped recently. We recommend the next ${weakestDomain.name} template with guided feedback checkpoints.`;
    }
    return 'Complete more projects to unlock a personalized next-step recommendation.';
  }, [lowestSkill, weakestDomain]);

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
    <section className="grid gap-5 lg:grid-cols-2">
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

      <article className="rounded-2xl border border-cyan-100 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">Sub-Skill Radar</h3>
        <p className="mb-3 text-sm text-slate-600">Your rubric profile to highlight strengths and gaps.</p>
        <div className="h-64">
          {radarData.length === 0 ? (
            <p className="pt-10 text-center text-sm text-slate-500">Sub-skill metrics will appear after evaluations.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="skill" tick={{ fontSize: 12 }} />
                <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Radar
                  name="Score"
                  dataKey="score"
                  stroke="#0284c7"
                  fill="#0ea5e9"
                  fillOpacity={0.35}
                  isAnimationActive
                />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </div>
      </article>

      <article className="rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 to-white p-5 shadow-sm lg:col-span-2">
        <h3 className="text-lg font-semibold text-slate-900">Recommended Next Step</h3>
        <p className="mt-1 text-sm text-slate-600">
          {recommendationText}
        </p>
        {(lowestSkill || weakestDomain) && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {lowestSkill && (
              <span className="rounded-full bg-rose-50 px-2.5 py-1 font-medium text-rose-700 ring-1 ring-rose-200">
                Lowest sub-skill: {lowestSkill.skill} ({lowestSkill.score.toFixed(1)})
              </span>
            )}
            {weakestDomain && (
              <span className="rounded-full bg-orange-50 px-2.5 py-1 font-medium text-orange-700 ring-1 ring-orange-200">
                Lowest domain: {weakestDomain.name} ({weakestDomain.avg.toFixed(1)})
              </span>
            )}
          </div>
        )}
      </article>
    </section>
  );
}
