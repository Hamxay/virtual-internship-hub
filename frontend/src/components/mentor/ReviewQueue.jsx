import React, { useCallback, useEffect, useState } from 'react';
import { mentorApi } from '../../api/mentor.api';
import SubmissionDetail from './SubmissionDetail';

function formatErr(err) {
  const d = err?.response?.data;
  if (!d) return err?.message || 'Request failed.';
  if (typeof d === 'string') return d;
  if (d.detail) return typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
  return JSON.stringify(d);
}

function latestScore(sub) {
  const evs = sub?.evaluations || [];
  if (!evs.length) return null;
  const ev = [...evs].sort((a, b) => new Date(b.reviewed_at || 0) - new Date(a.reviewed_at || 0))[0];
  return ev?.overall_score != null ? Number(ev.overall_score) : null;
}

function TriageBadge({ score }) {
  if (score == null || Number.isNaN(score)) return null;
  if (score < 60) {
    return (
      <span className="mt-1 inline-flex rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red-800 ring-1 ring-red-200">
        AI: Low score
      </span>
    );
  }
  if (score > 80) {
    return (
      <span className="mt-1 inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-800 ring-1 ring-emerald-200">
        AI: Looks good
      </span>
    );
  }
  return (
    <span className="mt-1 inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-900 ring-1 ring-amber-200">
      AI: Moderate
    </span>
  );
}

export default function ReviewQueue() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [mentorFeedback, setMentorFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await mentorApi.getReviewQueue();
      const list = Array.isArray(data) ? data : [];
      setRows(list);
      setSelectedId((prev) => {
        if (prev && list.some((r) => r.id === prev)) return prev;
        return list[0]?.id ?? null;
      });
    } catch (err) {
      setRows([]);
      setSelectedId(null);
      setError(formatErr(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    setMentorFeedback('');
  }, [selectedId]);

  useEffect(() => {
    if (!toast) return undefined;
    const t = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const selected = rows.find((r) => r.id === selectedId) || null;
  const feedbackMissing = mentorFeedback.trim() === '';

  const submitDecision = async (approved) => {
    if (!selected || feedbackMissing) return;
    const reviewedId = selected.id;
    const nextRows = rows.filter((r) => r.id !== reviewedId);
    setSubmitting(true);
    setError('');
    try {
      await mentorApi.submitReview({
        submission_id: reviewedId,
        mentor_feedback: mentorFeedback.trim(),
        approved,
      });
      setToast(approved ? 'Submission approved.' : 'Revision requested.');
      setRows(nextRows);
      setMentorFeedback('');
      setSelectedId(nextRows[0]?.id ?? null);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-[32rem] flex-col">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">
          AI-triaged items in your expertise domain. Select a row to review details.
        </p>
        <button
          type="button"
          onClick={loadQueue}
          disabled={loading}
          className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-60"
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          {error}
        </div>
      ) : null}

      {loading && rows.length === 0 ? (
        <div className="flex flex-1 items-center justify-center rounded-xl border border-slate-200 bg-white py-20 text-slate-500">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600" />
          <span className="ml-3 text-sm font-medium">Loading queue…</span>
        </div>
      ) : rows.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/80 py-16 text-center">
          <p className="text-sm font-medium text-slate-700">You&apos;re all caught up</p>
          <p className="mt-1 max-w-sm text-xs text-slate-500">No submissions need mentor review in your domain right now.</p>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 gap-4 lg:gap-6">
          <aside className="flex w-full max-w-full shrink-0 flex-col rounded-xl border border-slate-200 bg-white shadow-sm lg:w-80">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Needs review</span>
              <span className="rounded-full bg-slate-900 px-2 py-0.5 text-xs font-semibold text-white">{rows.length}</span>
            </div>
            <ul className="max-h-[70vh] flex-1 overflow-y-auto p-2">
              {rows.map((row) => {
                const title = row?.assignment?.project_template?.title || 'Project';
                const student = row?.assignment?.student;
                const name = student?.username || student?.email || 'Student';
                const active = row.id === selectedId;
                const score = latestScore(row);
                return (
                  <li key={row.id} className="mb-1">
                    <button
                      type="button"
                      onClick={() => setSelectedId(row.id)}
                      className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                        active
                          ? 'border-indigo-500 bg-indigo-50/90 ring-1 ring-indigo-500'
                          : 'border-transparent bg-white hover:border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="text-sm font-semibold leading-snug text-slate-900 line-clamp-2">{title}</div>
                      <div className="mt-0.5 text-xs text-slate-600">{name}</div>
                      <TriageBadge score={score} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>
          <SubmissionDetail
            submission={selected}
            mentorFeedback={mentorFeedback}
            onFeedbackChange={setMentorFeedback}
            onApprove={() => submitDecision(true)}
            onRequestRevision={() => submitDecision(false)}
            submitting={submitting}
            feedbackMissing={feedbackMissing}
          />
        </div>
      )}

      {toast ? (
        <div
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-900 shadow-lg"
          role="status"
        >
          {toast}
        </div>
      ) : null}
    </div>
  );
}
