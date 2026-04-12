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

export default function MentorReviewQueue() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [mentorNotes, setMentorNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionMessage, setActionMessage] = useState('');

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError('');
    setActionMessage('');
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
    setMentorNotes('');
    setActionMessage('');
  }, [selectedId]);

  const submitDecision = async (approved) => {
    if (!selected) return;
    setSubmitting(true);
    setError('');
    setActionMessage('');
    try {
      await mentorApi.submitReview({
        submission_id: selected.id,
        mentor_feedback: mentorNotes.trim(),
        approved,
      });
      setActionMessage(approved ? 'Marked complete for the student.' : 'Sent back for revision.');
      await loadQueue();
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
      {actionMessage && <p className="mentor-review-success">{actionMessage}</p>}

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
                    <span className="mentor-review-list-title">{submissionLabel(row)}</span>
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
                  <strong>{selected.assignment?.student?.username || selected.assignment?.student?.email || '—'}</strong>
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
                  value={mentorNotes}
                  onChange={(e) => setMentorNotes(e.target.value)}
                  placeholder="Explain what you reviewed, what should change, or what they did well."
                />
                <div className="mentor-review-buttons">
                  <button
                    type="button"
                    className="mentor-review-btn mentor-review-btn--approve"
                    disabled={submitting}
                    onClick={() => submitDecision(true)}
                  >
                    {submitting ? 'Saving…' : 'Approve & mark complete'}
                  </button>
                  <button
                    type="button"
                    className="mentor-review-btn mentor-review-btn--reject"
                    disabled={submitting}
                    onClick={() => submitDecision(false)}
                  >
                    Request revision
                  </button>
                </div>
                <p className="mentor-review-hint">
                  Approve closes the assignment as completed. Request revision sends it back so the student can resubmit.
                </p>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
