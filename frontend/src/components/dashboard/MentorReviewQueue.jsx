import { useCallback, useEffect, useState } from 'react';
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

function scoreClass(score) {
  if (score == null) return '';
  const n = Number(score);
  if (n >= 70) return 'mrq-score--high';
  if (n >= 40) return 'mrq-score--mid';
  return 'mrq-score--low';
}

function toImprovementList(improvements) {
  if (!improvements) return [];
  if (Array.isArray(improvements)) return improvements.filter(Boolean);
  if (typeof improvements === 'string') {
    return improvements.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

/* ── Icons ── */
function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}
function ExternalIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}
function GithubIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}
function LinkIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}
function FileIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}
function CheckIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
function InboxIcon() {
  return (
    <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </svg>
  );
}

/* ── Main component ── */
export default function MentorReviewQueue() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [mentorFeedback, setMentorFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!toast) return undefined;
    const t = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(t);
  }, [toast]);

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

  useEffect(() => { loadQueue(); }, [loadQueue]);

  const selected = rows.find((r) => r.id === selectedId) || null;
  useEffect(() => { setMentorFeedback(''); }, [selectedId]);

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
      setToast(approved ? 'Submission approved successfully!' : 'Revision requested — student notified.');
      setRows(nextRows);
      setMentorFeedback('');
      setSelectedId((prev) => (prev === reviewedId ? (nextRows[0]?.id ?? null) : prev));
    } catch (err) {
      setError(formatReviewError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const hasSubmissionContent = selected && (
    selected.repository_url || selected.artifact_url || selected.uploaded_file ||
    selected.submission_text || selected.notes
  );

  return (
    <div className="mrq-layout">
      {/* Page header */}
      <div className="mrq-toolbar">
        <div>
          <h2 className="mrq-page-title">Review Queue</h2>
          <p className="mrq-page-sub">
            Submissions flagged for mentor review in your expertise domain.
          </p>
        </div>
        <button type="button" className="mrq-refresh-btn" onClick={loadQueue} disabled={loading}>
          <RefreshIcon />
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && <div className="mrq-error-banner" role="alert">{error}</div>}

      {loading && rows.length === 0 ? (
        <div className="mrq-loading-state">
          <div className="mrq-spinner" />
          <span>Loading queue…</span>
        </div>
      ) : rows.length === 0 ? (
        <div className="mrq-empty-state">
          <InboxIcon />
          <h3>All caught up!</h3>
          <p>No submissions need your review right now. Check back later.</p>
        </div>
      ) : (
        <div className="mrq-panels">

          {/* ── Left: submission list ── */}
          <aside className="mrq-list-panel">
            <div className="mrq-list-header">
              <span className="mrq-list-label">Submissions</span>
              <span className="mrq-list-count">{rows.length}</span>
            </div>
            <ul className="mrq-list">
              {rows.map((row) => {
                const title = row?.assignment?.project_template?.title || 'Project';
                const student = row?.assignment?.student;
                const studentName = student?.username || student?.email || 'Unknown';
                const statusKey = (row.status || '').toLowerCase().replace(/_/g, '-');
                const isActive = row.id === selectedId;
                return (
                  <li key={row.id}>
                    <button
                      type="button"
                      className={`mrq-list-item${isActive ? ' is-active' : ''}`}
                      onClick={() => setSelectedId(row.id)}
                    >
                      <div className="mrq-list-item-main">
                        <span className="mrq-list-item-title">{title}</span>
                        <span className="mrq-list-item-student">{studentName}</span>
                        <span className="mrq-list-item-meta">
                          v{row.version} · {row.submitted_at ? new Date(row.submitted_at).toLocaleDateString() : '—'}
                        </span>
                      </div>
                      <span className={`mrq-pill mrq-pill--${statusKey}`}>
                        {(row.status || '—').replace(/_/g, ' ')}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>

          {/* ── Right: detail panel ── */}
          {selected && (
            <section className="mrq-detail-panel">

              {/* Header */}
              <div className="mrq-detail-header">
                <div className="mrq-detail-header-row">
                  <h3 className="mrq-detail-title">
                    {selected.assignment?.project_template?.title || 'Submission'}
                  </h3>
                  <span className={`mrq-pill mrq-pill--${(selected.status || '').toLowerCase().replace(/_/g, '-')}`}>
                    {(selected.status || '—').replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="mrq-student-row">
                  <div className="mrq-student-avatar">
                    {(selected.assignment?.student?.username || 'S')[0].toUpperCase()}
                  </div>
                  <div className="mrq-student-info">
                    {selected.assignment?.student?.username ? (
                      <a
                        href={`/portfolio/${encodeURIComponent(selected.assignment.student.username)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mrq-student-name-link"
                      >
                        {selected.assignment.student.username}
                        <ExternalIcon />
                      </a>
                    ) : (
                      <strong className="mrq-student-name">{selected.assignment?.student?.email || '—'}</strong>
                    )}
                    {selected.assignment?.student?.email &&
                     selected.assignment?.student?.username &&
                     selected.assignment.student.email !== selected.assignment.student.username && (
                      <span className="mrq-student-email">{selected.assignment.student.email}</span>
                    )}
                  </div>
                  <div className="mrq-meta-chips">
                    <span className="mrq-meta-chip">v{selected.version}</span>
                    <span className="mrq-meta-chip">{selected.assignment?.status?.replace(/_/g, ' ') || '—'}</span>
                  </div>
                </div>
              </div>

              {/* Submission content */}
              <div className="mrq-section">
                <h4 className="mrq-section-label">Submission Content</h4>

                {/* Links row */}
                {(selected.repository_url || selected.artifact_url || selected.uploaded_file) && (
                  <div className="mrq-links-row">
                    {selected.repository_url && (
                      <a href={selected.repository_url} target="_blank" rel="noopener noreferrer" className="mrq-link mrq-link--repo">
                        <GithubIcon /> Repository
                      </a>
                    )}
                    {selected.artifact_url && (
                      <a href={selected.artifact_url} target="_blank" rel="noopener noreferrer" className="mrq-link mrq-link--demo">
                        <LinkIcon /> Demo / Artifact
                      </a>
                    )}
                    {selected.uploaded_file && (
                      <a href={mediaOrAbsoluteUrl(selected.uploaded_file)} target="_blank" rel="noopener noreferrer" className="mrq-link mrq-link--file">
                        <FileIcon /> Download File
                      </a>
                    )}
                  </div>
                )}

                {/* Written content */}
                {selected.submission_text && (
                  <div className="mrq-text-block">
                    <span className="mrq-text-block-label">Student Summary</span>
                    <p className="mrq-text-block-body">{selected.submission_text}</p>
                  </div>
                )}
                {selected.notes && (
                  <div className="mrq-text-block">
                    <span className="mrq-text-block-label">Student Notes</span>
                    <p className="mrq-text-block-body">{selected.notes}</p>
                  </div>
                )}

                {/* No content notice */}
                {!hasSubmissionContent && (
                  <div className="mrq-no-content-notice">
                    <span className="mrq-no-content-icon">⚠</span>
                    <div>
                      <strong>No submission content available</strong>
                      <p>The student did not provide a repository URL, file upload, or written text. You can still leave feedback and request a revision.</p>
                    </div>
                  </div>
                )}
              </div>

              {/* AI evaluations */}
              <div className="mrq-section">
                <h4 className="mrq-section-label">AI Evaluation</h4>
                {(selected.evaluations || []).length === 0 ? (
                  <p className="mrq-muted-text">No automated evaluation has run yet.</p>
                ) : (
                  [...(selected.evaluations || [])]
                    .sort((a, b) => new Date(b.reviewed_at || 0) - new Date(a.reviewed_at || 0))
                    .map((ev) => {
                      const impList = toImprovementList(ev.improvements);
                      return (
                        <div key={ev.id} className="mrq-ev-card">
                          <div className="mrq-ev-top">
                            <div className={`mrq-ev-score ${scoreClass(ev.overall_score)}`}>
                              <span className="mrq-ev-score-num">{ev.overall_score ?? '—'}</span>
                              <span className="mrq-ev-score-denom">/100</span>
                            </div>
                            <div className="mrq-ev-badges">
                              <span className={`mrq-decision-badge mrq-decision-badge--${(ev.decision || '').toLowerCase().replace(/_/g, '-')}`}>
                                {(ev.decision || '—').replace(/_/g, ' ')}
                              </span>
                              {ev.is_human_reviewed && (
                                <span className="mrq-human-badge">
                                  <CheckIcon /> Human Reviewed
                                </span>
                              )}
                            </div>
                            {ev.model_name && (
                              <span className="mrq-ev-model">{ev.model_name}</span>
                            )}
                          </div>

                          {ev.feedback_summary && (
                            <p className="mrq-ev-summary">{ev.feedback_summary}</p>
                          )}

                          {impList.length > 0 && (
                            <div className="mrq-ev-improve">
                              <span className="mrq-text-block-label">AI Feedback</span>
                              <ul className="mrq-ev-improve-list">
                                {impList.map((t, i) => <li key={i}>{t}</li>)}
                              </ul>
                            </div>
                          )}

                          {Array.isArray(ev.extracted_tags) && ev.extracted_tags.length > 0 && (
                            <div className="mrq-ev-tags">
                              <span className="mrq-text-block-label">Detected Skills</span>
                              <div className="mrq-tags-row">
                                {ev.extracted_tags.map((tag, idx) => (
                                  <span key={`${ev.id}-t-${idx}`} className="mrq-tag">{tag}</span>
                                ))}
                              </div>
                            </div>
                          )}

                          {Array.isArray(ev.flags) && ev.flags.length > 0 && (
                            <p className="mrq-ev-flags">⚑ {ev.flags.join(' · ')}</p>
                          )}
                        </div>
                      );
                    })
                )}
              </div>

              {/* Feedback form */}
              <div className="mrq-feedback-section">
                <h4 className="mrq-section-label">Your Review</h4>
                <label className="mrq-feedback-label" htmlFor="mrq-feedback-input">
                  Feedback for the student <span className="mrq-required">*</span>
                </label>
                <textarea
                  id="mrq-feedback-input"
                  className="mrq-feedback-textarea"
                  rows={5}
                  value={mentorFeedback}
                  onChange={(e) => setMentorFeedback(e.target.value)}
                  placeholder="Describe what you reviewed, what the student did well, and what needs improvement."
                />
                {feedbackMissing && !submitting && (
                  <p className="mrq-feedback-warn">Please write feedback before submitting your review.</p>
                )}
                <div className="mrq-action-row">
                  <button
                    type="button"
                    className="mrq-btn mrq-btn--approve"
                    disabled={submitting || feedbackMissing}
                    onClick={() => submitDecision(true)}
                  >
                    <CheckIcon />
                    {submitting ? 'Saving…' : 'Approve & Complete'}
                  </button>
                  <button
                    type="button"
                    className="mrq-btn mrq-btn--revise"
                    disabled={submitting || feedbackMissing}
                    onClick={() => submitDecision(false)}
                  >
                    Request Revision
                  </button>
                </div>
                <p className="mrq-action-hint">
                  Approve marks the assignment as completed. Request revision sends it back for the student to resubmit.
                </p>
              </div>

            </section>
          )}
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className="mrq-toast" role="status" aria-live="polite">
          <span className="mrq-toast-icon"><CheckIcon /></span>
          {toast}
        </div>
      )}
    </div>
  );
}
