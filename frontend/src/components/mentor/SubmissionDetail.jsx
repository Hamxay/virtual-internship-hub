import React, { useMemo } from 'react';
import { mentorMediaAbsoluteUrl } from '../../utils/mentorMediaUrl';

function latestEvaluation(submission) {
  const list = submission?.evaluations || [];
  if (!list.length) return null;
  return [...list].sort((a, b) => new Date(b.reviewed_at || 0) - new Date(a.reviewed_at || 0))[0];
}

/**
 * @param {{
 *   submission: object | null,
 *   mentorFeedback: string,
 *   onFeedbackChange: (v: string) => void,
 *   onApprove: () => void,
 *   onRequestRevision: () => void,
 *   submitting: boolean,
 *   feedbackMissing: boolean,
 * }} props
 */
export default function SubmissionDetail({
  submission,
  mentorFeedback,
  onFeedbackChange,
  onApprove,
  onRequestRevision,
  submitting,
  feedbackMissing,
}) {
  const ev = useMemo(() => latestEvaluation(submission), [submission]);
  const scoreNum = ev?.overall_score != null ? Number(ev.overall_score) : null;

  if (!submission) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/60 p-12 text-center text-sm text-slate-500">
        Select a submission from the queue.
      </div>
    );
  }

  const title = submission.assignment?.project_template?.title || 'Submission';
  const student = submission.assignment?.student;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">{title}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {student?.username && (
                <span className="font-medium text-slate-800">{student.username}</span>
              )}
              {student?.email && (
                <span className="text-slate-500"> · {student.email}</span>
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              v{submission.version}
            </span>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              {(submission.status || '—').replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-8 px-6 py-6">
        {/* Section A — Submitted work */}
        <section>
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Submitted work</h3>
          <div className="flex flex-wrap gap-2">
            {submission.uploaded_file ? (
              <a
                href={mentorMediaAbsoluteUrl(submission.uploaded_file)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
              >
                Download file
              </a>
            ) : null}
            {submission.repository_url ? (
              <a
                href={submission.repository_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 shadow-sm transition hover:bg-slate-50"
              >
                View repository
              </a>
            ) : null}
            {submission.artifact_url ? (
              <a
                href={submission.artifact_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 shadow-sm transition hover:bg-slate-50"
              >
                Open artifact
              </a>
            ) : null}
          </div>
          {submission.submission_text ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50/80 p-4">
              <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Student summary</p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{submission.submission_text}</p>
            </div>
          ) : null}
          {!submission.uploaded_file && !submission.repository_url && !submission.artifact_url && !submission.submission_text ? (
            <p className="text-sm text-amber-800">No file, link, or text was provided for this submission.</p>
          ) : null}
        </section>

        {/* Section B — AI feedback */}
        <section>
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">AI evaluation</h3>
          {ev ? (
            <div className="rounded-xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white p-5">
              <div className="flex flex-wrap items-baseline gap-3">
                <span className={`text-3xl font-bold tabular-nums ${scoreNum != null && scoreNum < 60 ? 'text-red-600' : 'text-slate-900'}`}>
                  {ev.overall_score ?? '—'}
                </span>
                <span className="text-lg font-medium text-slate-400">/ 100</span>
                {ev.model_name ? (
                  <span className="ml-auto rounded-full bg-slate-200/80 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                    {ev.model_name}
                  </span>
                ) : null}
              </div>
              {ev.feedback_summary ? (
                <div className="mt-4 border-t border-slate-200/80 pt-4">
                  <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Feedback summary</p>
                  <p className="text-sm leading-relaxed text-slate-700">{ev.feedback_summary}</p>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No AI evaluation is attached to this submission.</p>
          )}
        </section>

        {/* Section C — Your review */}
        <section>
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Your review</h3>
          <label htmlFor="mentor-review-feedback" className="mb-1 block text-sm font-medium text-slate-700">
            Feedback for the student <span className="text-red-500">*</span>
          </label>
          <textarea
            id="mentor-review-feedback"
            rows={5}
            value={mentorFeedback}
            onChange={(e) => onFeedbackChange(e.target.value)}
            placeholder="Summarize what you verified, strengths, and what must change before approval."
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          {feedbackMissing && !submitting ? (
            <p className="mt-1 text-xs text-amber-700">Feedback is required before you can submit a decision.</p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={submitting || feedbackMissing}
              onClick={onApprove}
              className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Saving…' : 'Approve submission'}
            </button>
            <button
              type="button"
              disabled={submitting || feedbackMissing}
              onClick={onRequestRevision}
              className="inline-flex items-center justify-center rounded-lg border border-red-200 bg-white px-5 py-2.5 text-sm font-semibold text-red-700 shadow-sm transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Saving…' : 'Request revision'}
            </button>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Approve completes the assignment. Request revision sends it back to the student with your notes.
          </p>
        </section>
      </div>
    </div>
  );
}
