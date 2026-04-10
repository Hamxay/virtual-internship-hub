import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { studentApi } from '../../api/student.api';
import {
  buildProjectSubmissionPayload,
  formatSubmissionError,
  isFileSubmissionType,
} from '../../services/student.service';

const EMPTY_SUBMISSION_FORM = {
  repository_url: '',
  artifact_url: '',
  submission_text: '',
  notes: '',
  submitted_files: '',
};

function statusBadgeClass(status) {
  if (status === 'COMPLETED') return 'complete';
  if (status === 'NEEDS_REVISION') return 'danger';
  if (status === 'RECOMMENDED') return 'recommended';
  return 'beginner';
}

/** Full project details — shown only when the row is expanded. */
function TaskExpandedDetails({ assignment }) {
  const template = assignment.project_template || {};
  const inst = template.instruction || {};
  const latestEvaluation = assignment.latest_submission?.evaluations?.[0];
  const submissionReqs = Array.isArray(inst.submission_requirements) ? inst.submission_requirements : [];
  const deliverables = Array.isArray(inst.deliverables) ? inst.deliverables : [];
  const steps = Array.isArray(inst.steps) ? inst.steps : [];
  const hasMoreBrief = Boolean(
    (template.business_problem && String(template.business_problem).trim())
    || (inst.overview && String(inst.overview).trim())
    || steps.length
    || deliverables.length,
  );

  return (
    <div className="student-task-expand">
      {template.short_description ? (
        <p className="student-task-expand__summary">{template.short_description}</p>
      ) : null}

      {assignment.recommendation_reason ? (
        <div className="student-task-card__why student-task-expand__why">
          <span className="student-task-card__why-label">Why recommended</span>
          <p className="student-task-card__why-text">{assignment.recommendation_reason}</p>
        </div>
      ) : null}

      {(template.tags || []).length > 0 ? (
        <div className="project-chip-row student-task-card__tags">
          {(template.tags || []).slice(0, 12).map((tag) => (
            <span key={tag} className="project-chip">{tag}</span>
          ))}
        </div>
      ) : null}

      {submissionReqs.length > 0 && (
        <section className="student-task-section">
          <div className="admin-template-preview-label">Submission requirements</div>
          <ul className="admin-template-bullet-list">
            {submissionReqs.map((line, idx) => (
              <li key={idx}>{String(line)}</li>
            ))}
          </ul>
        </section>
      )}

      {hasMoreBrief && (
        <details className="student-task-more">
          <summary>Scenario, full brief, steps &amp; deliverables</summary>
          <div className="student-task-inner">
            {template.business_problem && String(template.business_problem).trim() ? (
              <div>
                <div className="admin-template-preview-label">Business scenario</div>
                <p className="student-task-text">{template.business_problem}</p>
              </div>
            ) : null}
            {inst.overview && String(inst.overview).trim() ? (
              <div>
                <div className="admin-template-preview-label">Full project brief</div>
                <p className="student-task-text">{inst.overview}</p>
              </div>
            ) : null}
            {steps.length > 0 ? (
              <div>
                <div className="admin-template-preview-label">Steps</div>
                <ol className="admin-template-bullet-list student-task-steps-list">
                  {steps.map((line, idx) => (
                    <li key={idx}>{String(line)}</li>
                  ))}
                </ol>
              </div>
            ) : null}
            {deliverables.length > 0 ? (
              <div>
                <div className="admin-template-preview-label">Deliverables checklist</div>
                <ul className="admin-template-bullet-list">
                  {deliverables.map((line, idx) => (
                    <li key={idx}>{String(line)}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </details>
      )}

      <div className="student-task-card__stats student-task-expand__stats">
        <div className="student-task-stat">
          <span className="student-task-stat__label">Last score</span>
          <span className="student-task-stat__value">{assignment.latest_evaluation_score ?? 'Not evaluated yet'}</span>
        </div>
        <div className="student-task-stat">
          <span className="student-task-stat__label">Prerequisites</span>
          <span className="student-task-stat__value">
            {(template.prerequisite_skills || []).join(' • ') || '—'}
          </span>
        </div>
      </div>

      {latestEvaluation && (
        <div className="task-feedback-box">
          <strong>AI feedback</strong>
          <p className="student-task-card__feedback-lead">{latestEvaluation.feedback_summary}</p>
          {Array.isArray(latestEvaluation.improvements) && latestEvaluation.improvements.length > 0 && (
            <p className="student-task-card__feedback-improve">
              Improve: {latestEvaluation.improvements.slice(0, 3).join(' • ')}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function TaskAssignmentsTable({
  assignments,
  expandedId,
  onToggleRow,
  onAccept,
  onOpenSubmit,
}) {
  if (assignments.length === 0) return null;

  return (
    <div className="student-task-table-wrap">
      <table className="student-task-table">
        <thead>
          <tr>
            <th className="student-task-table__th-chev" aria-hidden="true" />
            <th>Domain</th>
            <th>Project</th>
            <th>Details</th>
            <th>Status</th>
            <th className="student-task-table__th-actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          {assignments.map((assignment) => {
            const template = assignment.project_template || {};
            const metaLine = [template.complexity, template.submission_type, template.estimated_hours != null ? `${template.estimated_hours}h` : null]
              .filter(Boolean)
              .join(' • ') || '—';
            const expanded = expandedId === assignment.id;
            return (
              <React.Fragment key={assignment.id}>
                <tr
                  className={`student-task-table__row ${expanded ? 'is-expanded' : ''}`}
                  onClick={() => onToggleRow(assignment.id)}
                >
                  <td className="student-task-table__chev" aria-hidden="true">{expanded ? '▼' : '▶'}</td>
                  <td className="student-task-table__domain">{template.domain?.name || '—'}</td>
                  <td className="student-task-table__title">{template.title || 'Project'}</td>
                  <td className="student-task-table__meta">{metaLine}</td>
                  <td>
                    <span className={`task-badge ${statusBadgeClass(assignment.status)}`}>
                      {assignment.status.replaceAll('_', ' ')}
                    </span>
                  </td>
                  <td className="student-task-table__actions" onClick={(e) => e.stopPropagation()}>
                    {assignment.status === 'RECOMMENDED' && (
                      <button type="button" className="btn-primary-green btn-table-action" onClick={() => onAccept(assignment.id)}>
                        Accept
                      </button>
                    )}
                    {['IN_PROGRESS', 'NEEDS_REVISION'].includes(assignment.status) && (
                      <button
                        type="button"
                        className="btn-primary btn-table-action"
                        onClick={() => onOpenSubmit(assignment)}
                      >
                        {assignment.status === 'NEEDS_REVISION' ? 'Resubmit' : 'Submit'}
                      </button>
                    )}
                  </td>
                </tr>
                {expanded ? (
                  <tr className="student-task-table__detail-row">
                    <td colSpan={6}>
                      <TaskExpandedDetails assignment={assignment} />
                    </td>
                  </tr>
                ) : null}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function StudentTasksSection({ assessmentPassed, onStartAssessment, onStatsChange }) {
  const [assignments, setAssignments] = useState([]);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshingRecommendations, setRefreshingRecommendations] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('recommended');
  const [submissionTarget, setSubmissionTarget] = useState(null);
  const [submissionForm, setSubmissionForm] = useState(EMPTY_SUBMISSION_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [expandedAssignmentId, setExpandedAssignmentId] = useState(null);
  const fileInputRef = useRef(null);

  const closeSubmitModal = useCallback(() => {
    setSubmissionTarget(null);
    setSubmissionForm(EMPTY_SUBMISSION_FORM);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const openSubmitModal = useCallback((target) => {
    setSubmissionForm(EMPTY_SUBMISSION_FORM);
    setSubmissionTarget(target);
    queueMicrotask(() => {
      if (fileInputRef.current) fileInputRef.current.value = '';
    });
  }, []);

  const loadAssignments = useCallback(async () => {
    try {
      const [assignmentRes, progressRes] = await Promise.all([
        studentApi.getAssignments(),
        studentApi.getProgressSnapshot(),
      ]);
      const assignmentData = assignmentRes?.data;
      const list = Array.isArray(assignmentData) ? assignmentData : (assignmentData?.results || []);
      setAssignments(list);
      setProgress(progressRes?.data || null);
      if (typeof onStatsChange === 'function') {
        onStatsChange({
          completed: list.filter((item) => item.status === 'COMPLETED').length,
          inProgress: list.filter((item) => ['IN_PROGRESS', 'NEEDS_REVISION', 'SUBMITTED'].includes(item.status)).length,
        });
      }
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load tasks.');
    } finally {
      setLoading(false);
    }
  }, [onStatsChange]);

  const refreshRecommendations = useCallback(async () => {
    setRefreshingRecommendations(true);
    try {
      await studentApi.getRecommendedProjects();
      await loadAssignments();
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load recommendations.');
    } finally {
      setRefreshingRecommendations(false);
    }
  }, [loadAssignments]);

  useEffect(() => {
    if (!assessmentPassed) {
      setLoading(false);
      return;
    }
    setLoading(true);
    refreshRecommendations().finally(() => setLoading(false));
  }, [assessmentPassed, refreshRecommendations]);

  useEffect(() => {
    setExpandedAssignmentId(null);
  }, [activeTab]);

  const sortByAssignedAtDesc = (a, b) => {
    const ta = a.assigned_at ? new Date(a.assigned_at).getTime() : 0;
    const tb = b.assigned_at ? new Date(b.assigned_at).getTime() : 0;
    return tb - ta;
  };

  /** FR3: split recommended rows by ``recommendation_source`` (legacy null → content feed). */
  const recommendedFeeds = useMemo(() => {
    const recommendedRows = assignments.filter((item) => item.status === 'RECOMMENDED');
    const contentBasedRows = recommendedRows
      .filter((item) => item.recommendation_source !== 'COLLABORATIVE')
      .sort(sortByAssignedAtDesc);
    const collaborativeRows = recommendedRows
      .filter((item) => item.recommendation_source === 'COLLABORATIVE')
      .sort(sortByAssignedAtDesc);
    return { contentBasedRows, collaborativeRows };
  }, [assignments]);

  const filteredAssignments = useMemo(() => {
    if (activeTab === 'recommended') {
      return [...recommendedFeeds.contentBasedRows, ...recommendedFeeds.collaborativeRows];
    }
    if (activeTab === 'active') return assignments.filter((item) => ['IN_PROGRESS', 'SUBMITTED', 'NEEDS_REVISION'].includes(item.status));
    return assignments.filter((item) => item.status === 'COMPLETED');
  }, [activeTab, assignments, recommendedFeeds]);

  const toggleRow = useCallback((id) => {
    setExpandedAssignmentId((prev) => (prev === id ? null : id));
  }, []);

  const acceptProject = async (assignmentId) => {
    try {
      await studentApi.acceptProject(assignmentId);
      await loadAssignments();
      setActiveTab('active');
      setExpandedAssignmentId(null);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not accept project.');
    }
  };

  const submitProject = async (event) => {
    event.preventDefault();
    if (!submissionTarget) return;
    const template = submissionTarget.project_template;
    setSubmitting(true);
    setError('');
    try {
      const payload = buildProjectSubmissionPayload(
        { ...submissionForm, uploaded_file: fileInputRef.current?.files?.[0] },
        template,
      );
      await studentApi.submitProject(submissionTarget.id, payload);
      closeSubmitModal();
      await loadAssignments();
      setActiveTab('active');
    } catch (err) {
      setError(err.response ? formatSubmissionError(err) : err.message || 'Submit failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const modalSt = submissionTarget?.project_template?.submission_type;
  const modalIsCode = Boolean(submissionTarget) && modalSt === 'CODE';
  const modalIsFile = Boolean(submissionTarget) && isFileSubmissionType(modalSt);

  if (!assessmentPassed) {
    return (
      <div className="dashboard-section">
        <h1>My Tasks</h1>
        <p className="section-desc">Complete the skill assessment first to unlock project recommendations.</p>
        <div className="tasks-locked-block">
          <p style={{ color: '#6b7280', marginBottom: '1rem' }}>Your personalized projects will appear here after assessment.</p>
          <button type="button" onClick={onStartAssessment} className="btn-outline-primary">Go to Assessment</button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-section">
      <div className="student-tasks-toolbar">
        <div className="student-tasks-toolbar__text">
          <h1>My Tasks</h1>
          <p className="section-desc">Click a row to expand full brief and requirements. Use Submit to open the submission form.</p>
        </div>
        <button type="button" className="btn-outline-small student-tasks-toolbar__refresh" onClick={refreshRecommendations} disabled={refreshingRecommendations}>
          {refreshingRecommendations ? 'Refreshing…' : 'Refresh recommendations'}
        </button>
      </div>

      {error && <p className="student-tasks-error">{error}</p>}

      {progress && (
        <div className="project-metric-grid" style={{ marginBottom: '1.25rem' }}>
          <div className="project-metric-card">
            <div className="project-metric-label">Completed</div>
            <div className="project-metric-value">{progress.completed_projects}</div>
          </div>
          <div className="project-metric-card">
            <div className="project-metric-label">Average Score</div>
            <div className="project-metric-value">{progress.average_score}</div>
          </div>
          <div className="project-metric-card">
            <div className="project-metric-label">Current Band</div>
            <div className="project-metric-value">{progress.current_complexity_band}</div>
          </div>
          <div className="project-metric-card">
            <div className="project-metric-label">Strongest Domain</div>
            <div className="project-metric-value">{progress.strongest_domain?.name || '—'}</div>
          </div>
        </div>
      )}

      <div className="student-tasks-tabs" role="tablist" aria-label="Task lists">
        <button type="button" role="tab" aria-selected={activeTab === 'recommended'} className={activeTab === 'recommended' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('recommended')}>Recommended</button>
        <button type="button" role="tab" aria-selected={activeTab === 'active'} className={activeTab === 'active' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('active')}>Active</button>
        <button type="button" role="tab" aria-selected={activeTab === 'completed'} className={activeTab === 'completed' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('completed')}>Completed</button>
      </div>

      {loading ? (
        <p style={{ color: '#6b7280' }}>Loading tasks...</p>
      ) : activeTab === 'recommended' &&
        recommendedFeeds.contentBasedRows.length === 0 &&
        recommendedFeeds.collaborativeRows.length === 0 ? (
        <div className="info-card">
          <p>
            No recommendations yet. Refresh recommendations or complete a project to improve personalization.
          </p>
        </div>
      ) : activeTab !== 'recommended' && filteredAssignments.length === 0 ? (
        <div className="info-card">
          <p>{activeTab === 'active' ? 'No active assignments yet.' : 'No completed projects yet.'}</p>
        </div>
      ) : activeTab === 'recommended' ? (
        <div className="student-recommended-feeds">
          {recommendedFeeds.contentBasedRows.length > 0 && (
            <section className="student-recommended-feed-section" aria-labelledby="feed-content-heading">
              <h2 id="feed-content-heading" className="student-recommended-feed-heading">
                For you (assessment &amp; your progress)
              </h2>
              <p className="student-recommended-feed-desc">
                Matched from your domain profile and completed project tags.
              </p>
              <TaskAssignmentsTable
                assignments={recommendedFeeds.contentBasedRows}
                expandedId={expandedAssignmentId}
                onToggleRow={toggleRow}
                onAccept={acceptProject}
                onOpenSubmit={openSubmitModal}
              />
            </section>
          )}
          {recommendedFeeds.collaborativeRows.length > 0 && (
            <section className="student-recommended-feed-section" aria-labelledby="feed-collab-heading">
              <h2 id="feed-collab-heading" className="student-recommended-feed-heading">
                Community-based picks
              </h2>
              <p className="student-recommended-feed-desc">
                Suggested from patterns across other students&apos; performance (collaborative filtering).
              </p>
              <TaskAssignmentsTable
                assignments={recommendedFeeds.collaborativeRows}
                expandedId={expandedAssignmentId}
                onToggleRow={toggleRow}
                onAccept={acceptProject}
                onOpenSubmit={openSubmitModal}
              />
            </section>
          )}
        </div>
      ) : (
        <TaskAssignmentsTable
          assignments={filteredAssignments}
          expandedId={expandedAssignmentId}
          onToggleRow={toggleRow}
          onAccept={acceptProject}
          onOpenSubmit={openSubmitModal}
        />
      )}

      {submissionTarget && (
        <div className="project-modal-overlay" onClick={closeSubmitModal}>
          <div className="project-modal-card" onClick={(event) => event.stopPropagation()}>
            <h2 style={{ marginTop: 0 }}>Submit project</h2>
            <p style={{ color: '#6b7280', marginTop: 0 }}>{submissionTarget.project_template?.title}</p>
            <form onSubmit={submitProject} className="project-form-grid">
              {modalIsCode && (
                <label className="project-form-span-2">
                  <span>Repository URL (required)</span>
                  <input
                    required
                    type="text"
                    inputMode="url"
                    autoComplete="url"
                    placeholder="https://github.com/org/repo"
                    value={submissionForm.repository_url}
                    onChange={(e) => setSubmissionForm((prev) => ({ ...prev, repository_url: e.target.value }))}
                  />
                </label>
              )}
              {modalIsFile && (
                <label className="project-form-span-2">
                  <span>Upload file (required, max 15 MB)</span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    required
                    accept=".pdf,.doc,.docx,.xlsx,.xls,.txt,.png,.jpg,.jpeg,.gif,.webp"
                  />
                </label>
              )}
              {!modalIsCode && !modalIsFile && (
                <label className="project-form-span-2">
                  <span>Repository URL</span>
                  <input value={submissionForm.repository_url} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, repository_url: e.target.value }))} />
                </label>
              )}
              <label className="project-form-span-2">
                <span>Artifact URL {modalIsCode || modalIsFile ? '(optional)' : ''}</span>
                <input value={submissionForm.artifact_url} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, artifact_url: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Submission summary {modalIsFile ? '(optional)' : ''}</span>
                <textarea rows={5} value={submissionForm.submission_text} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submission_text: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Notes (optional)</span>
                <textarea rows={3} value={submissionForm.notes} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>
              {(modalIsCode || (!modalIsCode && !modalIsFile)) && (
                <label className="project-form-span-2">
                  <span>Submitted files list (one per line, optional)</span>
                  <textarea rows={3} value={submissionForm.submitted_files} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submitted_files: e.target.value }))} />
                </label>
              )}
              <p className="project-form-span-2" style={{ margin: 0, fontSize: '0.8125rem', color: '#64748b' }}>
                AI evaluation runs in the background. Refresh My Tasks in a few seconds to see your score.
              </p>
              <div className="project-form-actions project-form-span-2">
                <button type="submit" className="btn-primary-green" disabled={submitting}>
                  {submitting ? 'Submitting...' : 'Submit for AI review'}
                </button>
                <button type="button" className="btn-outline-small" onClick={closeSubmitModal}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
