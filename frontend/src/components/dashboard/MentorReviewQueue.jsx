import React, { useCallback, useEffect, useState } from 'react';
import { API_BASE_URL } from '../../api/client';
import { mentorApi } from '../../api/mentor.api';

function mediaOrAbsoluteUrl(path) {
  if (!path) return '';
  const s = String(path);
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  const origin = API_BASE_URL.replace(/\/api\/?$/, '');
  return s.startsWith('/') ? `${origin}${s}` : `${origin}/${s}`;
}

function formatReviewError(err) {
  const d = err?.response?.data;
  if (!d) return err?.message || 'Request failed.';
  if (typeof d === 'string') return d;
  if (d.detail) return typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
  return JSON.stringify(d);
}

function submissionLabel(row) {
  const title = row?.assignment?.project_template?.title || 'Project';
  const student = row?.assignment?.student;
  const who = student ? `${student.username || student.email}` : 'Student';
  return `${title} — ${who}`;
}

function StudentPortfolioExternalIcon({ username, className = '' }) {
  if (!username) return null;
  const href = `/portfolio/${encodeURIComponent(username)}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title="View Student's Public Portfolio"
      aria-label="View Student's Public Portfolio"
      className={className}
      onClick={(e) => e.stopPropagation()}
    >
      <span className="mentor-review-portfolio-ext-icon" aria-hidden>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
          <polyline points="15 3 21 3 21 9" />
          <line x1="10" y1="14" x2="21" y2="3" />
        </svg>
      </span>
    </a>
  );
}

export default function MentorReviewQueue() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [mentorFeedback, setMentorFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  useEffect(() => {
    if (!toastMessage) return undefined;
    const t = window.setTimeout(() => setToastMessage(null), 4000);
    return () => window.clearTimeout(t);
  }, [toastMessage]);

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
      setError(formatReviewError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const selected = rows.find((r) => r.id === selectedId) || null;

  useEffect(() => {
    setMentorFeedback('');
  }, [selectedId]);

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
      setToastMessage('Review Submitted Successfully!');
      setRows(nextRows);
      setMentorFeedback('');
      setSelectedId((prev) => (prev === reviewedId ? (nextRows[0]?.id ?? null) : prev));
    } catch (err) {
      setError(formatReviewError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mentor-review-layout">
      <div className="mentor-review-toolbar">
        <h2 className="mentor-review-title">Review queue</h2>
        <p className="mentor-review-sub">
          Submissions flagged by the system or marked for mentor review in your expertise domain.
        </p>
        <button type="button" className="mentor-review-refresh" onClick={loadQueue} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh queue'}
        </button>
      </div>

      {error && <p className="mentor-review-error" role="alert">{error}</p>}

      {loading && rows.length === 0 ? (
        <p className="mentor-loading">Loading queue…</p>
      ) : rows.length === 0 ? (
        <div className="mentor-section-card mentor-review-empty">
          <p>No submissions need your review right now.</p>
        </div>
      ) : (
        <div className="mentor-review-panels">
          <aside className="mentor-review-list-wrap">
            <ul className="mentor-review-list">
              {rows.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className={`mentor-review-list-item${row.id === selectedId ? ' is-active' : ''}`}
                    onClick={() => setSelectedId(row.id)}
                  >
                    <span className="mentor-review-list-title">
                      {submissionLabel(row)}
                      <StudentPortfolioExternalIcon username={row?.assignment?.student?.username} className="mentor-review-list-portfolio-link" />
                    </span>
                    <span className={`mentor-review-pill mentor-review-pill--${(row.status || '').toLowerCase()}`}>
                      {row.status || '—'}
                    </span>
                    <span className="mentor-review-list-meta">
                      v{row.version} · {row.submitted_at ? new Date(row.submitted_at).toLocaleString() : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          {selected && (
            <section className="mentor-review-detail">
              <header className="mentor-review-detail-head">
                <h3>{selected.assignment?.project_template?.title || 'Submission'}</h3>
                <p className="mentor-review-detail-student">
                  Student:{' '}
                  {selected.assignment?.student?.username ? (
                    <strong>
                      <a
                        href={`/portfolio/${encodeURIComponent(selected.assignment.student.username)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="View Student's Public Portfolio"
                        className="mentor-review-student-portfolio-link"
                      >
                        {selected.assignment.student.username}
                      </a>
                    </strong>
                  ) : (
                    <strong>{selected.assignment?.student?.email || '—'}</strong>
                  )}
                  <StudentPortfolioExternalIcon username={selected.assignment?.student?.username} className="mentor-review-detail-portfolio-icon" />
                  {selected.assignment?.student?.email && selected.assignment?.student?.username
                  && selected.assignment.student.email !== selected.assignment.student.username ? (
                    <span className="mentor-review-detail-email"> ({selected.assignment.student.email})</span>
                    ) : null}
                </p>
                <p className="mentor-review-detail-assign">
                  Assignment status: <strong>{selected.assignment?.status?.replace(/_/g, ' ') || '—'}</strong>
                  {' · '}
                  Submission: <strong>{selected.status}</strong>
                </p>
              </header>

              <div className="mentor-review-links">
                {selected.repository_url ? (
                  <a href={selected.repository_url} target="_blank" rel="noopener noreferrer" className="mentor-review-link">
                    Open repository link
                  </a>
                ) : null}
                {selected.artifact_url ? (
                  <a href={selected.artifact_url} target="_blank" rel="noopener noreferrer" className="mentor-review-link">
                    Open demo / file link
                  </a>
                ) : null}
                {selected.uploaded_file ? (
                  <a
                    href={mediaOrAbsoluteUrl(selected.uploaded_file)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mentor-review-link"
                  >
                    Download uploaded file
                  </a>
                ) : null}
              </div>

              {(selected.submission_text || selected.notes) && (
                <div className="mentor-review-student-text">
                  {selected.submission_text ? (
                    <div>
                      <h4>Student summary</h4>
                      <p>{selected.submission_text}</p>
                    </div>
                  ) : null}
                  {selected.notes ? (
                    <div>
                      <h4>Student notes</h4>
                      <p>{selected.notes}</p>
                    </div>
                  ) : null}
                </div>
              )}

              <div className="mentor-review-evaluations">
                <h4>Automated evaluations</h4>
                {(selected.evaluations || []).length === 0 ? (
                  <p className="mentor-review-muted">No evaluation rows attached.</p>
                ) : (
                  [...(selected.evaluations || [])]
                    .sort((a, b) => new Date(b.reviewed_at || 0) - new Date(a.reviewed_at || 0))
                    .map((ev) => (
                      <article key={ev.id} className="mentor-review-ev-card">
                        <div className="mentor-review-ev-head">
                          <span className="mentor-review-ev-score">Score {ev.overall_score ?? '—'}</span>
                          <span className="mentor-review-ev-decision">{ev.decision?.replace(/_/g, ' ')}</span>
                          {ev.is_human_reviewed ? <span className="mentor-review-ev-reviewed">Reviewed</span> : null}
                        </div>
                        {ev.feedback_summary ? <p className="mentor-review-ev-summary">{ev.feedback_summary}</p> : null}
                        {Array.isArray(ev.improvements) && ev.improvements.length > 0 ? (
                          <ul className="mentor-review-ev-improve">
                            {ev.improvements.map((t, i) => (
                              <li key={i}>{t}</li>
                            ))}
                          </ul>
                        ) : null}
                        {Array.isArray(ev.extracted_tags) && ev.extracted_tags.length > 0 ? (
                          <div className="mentor-review-ev-tags mt-3">
                            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
                              AI-detected tags
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {ev.extracted_tags.map((tag, idx) => (
                                <span
                                  key={`${ev.id}-tag-${idx}`}
                                  className="inline-flex items-center rounded-full bg-slate-200 px-3 py-1 text-xs font-medium text-slate-800 ring-1 ring-inset ring-slate-400/30"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        {Array.isArray(ev.flags) && ev.flags.length > 0 ? (
                          <p className="mentor-review-ev-flags">
                            Flags: {ev.flags.join(', ')}
                          </p>
                        ) : null}
                      </article>
                    ))
                )}
              </div>

              <div className="mentor-review-actions-block">
                <label className="mentor-form-label" htmlFor="mentor-review-feedback">
                  Your feedback for the student
                </label>
                <textarea
                  id="mentor-review-feedback"
                  className="mentor-form-input mentor-form-textarea mentor-review-textarea"
                  rows={5}
                  value={mentorFeedback}
                  onChange={(e) => setMentorFeedback(e.target.value)}
                  placeholder="Explain what you reviewed, what should change, or what they did well."
                />
                <div className="mentor-review-buttons">
                  <button
                    type="button"
                    className="mentor-review-btn mentor-review-btn--approve"
                    disabled={submitting || feedbackMissing}
                    title={feedbackMissing ? 'Feedback is required before submitting' : undefined}
                    onClick={() => submitDecision(true)}
                  >
                    {submitting ? 'Saving…' : 'Approve & mark complete'}
                  </button>
                  <button
                    type="button"
                    className="mentor-review-btn mentor-review-btn--reject"
                    disabled={submitting || feedbackMissing}
                    title={feedbackMissing ? 'Feedback is required before submitting' : undefined}
                    onClick={() => submitDecision(false)}
                  >
                    Request revision
                  </button>
                </div>
                {feedbackMissing && !submitting ? (
                  <p className="mt-2 text-sm text-slate-500">
                    Feedback is required before submitting.
                  </p>
                ) : null}
                <p className="mentor-review-hint">
                  Approve closes the assignment as completed. Request revision sends it back so the student can resubmit.
                </p>
              </div>
            </section>
          )}
        </div>
      )}

      {toastMessage ? (
        <div
          className="fixed bottom-6 right-6 z-[100] max-w-sm rounded-lg border border-emerald-600/40 bg-emerald-950 px-4 py-3 text-sm font-medium text-emerald-50 shadow-lg shadow-emerald-950/40"
          role="status"
          aria-live="polite"
        >
          {toastMessage}
        </div>
      ) : null}
    </div>
  );
}
