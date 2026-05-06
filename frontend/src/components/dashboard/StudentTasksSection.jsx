import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { studentApi } from '../../api/student.api';
import {
  buildProjectSubmissionPayload,
  formatSubmissionError,
} from '../../services/student.service';
import {
  friendlyRequirementLine,
  handInTypeLabel,
  levelLabel,
  projectSummaryLine,
  taskStatusLabel,
} from '../../services/studentTasksLabels';

/** Form state keys match the API; labels in JSX are plain English. */
const EMPTY_SUBMISSION_FORM = {
  submission_text: '',
  notes: '',
  submitted_files: '',
};

/** Assignment waiting on Celery + Gemini (submission row still SUBMITTED). */
function isAiEvaluationPending(assignment) {
  return (
    assignment.status === 'SUBMITTED'
    && assignment.latest_submission?.status === 'SUBMITTED'
  );
}

function getExtractedTags(submission, evaluation) {
  const fromRubric = evaluation?.rubric_scores?.extracted_tags;
  const fromMeta = submission?.metadata?.fr4_extracted_tags;
  if (Array.isArray(fromRubric) && fromRubric.length) return fromRubric;
  if (Array.isArray(fromMeta) && fromMeta.length) return fromMeta;
  return [];
}

function formatImprovementsBlock(evaluation) {
  if (!evaluation?.improvements) return '';
  const { improvements } = evaluation;
  if (typeof improvements === 'string') return improvements.trim();
  if (Array.isArray(improvements)) {
    return improvements.map((s) => String(s).trim()).filter(Boolean).join('\n\n');
  }
  return '';
}

function statusBadgeClass(status) {
  if (status === 'COMPLETED') return 'complete';
  if (status === 'NEEDS_REVISION') return 'danger';
  if (status === 'RECOMMENDED') return 'recommended';
  if (status === 'PENDING_MENTOR_REVIEW') return 'recommended';
  return 'beginner';
}

/** Project details popup — shows on card click. */
function ProjectDetailsModal({ assignment, onClose, onOpenSubmit }) {
  const template = assignment.project_template || {};
  const inst = template.instruction || {};
  const submissionReqs = Array.isArray(inst.submission_requirements) ? inst.submission_requirements : [];
  const deliverables = Array.isArray(inst.deliverables) ? inst.deliverables : [];
  const steps = Array.isArray(inst.steps) ? inst.steps : [];
  const hasInstructions = Boolean(
    (template.business_problem && String(template.business_problem).trim())
    || (inst.overview && String(inst.overview).trim())
    || steps.length
    || deliverables.length,
  );
  const canSubmit = ['IN_PROGRESS', 'NEEDS_REVISION'].includes(assignment.status);
  const isEvaluating = isAiEvaluationPending(assignment);
  const summary = projectSummaryLine(template);

  const sub = assignment.latest_submission;
  const ev = sub?.evaluations?.[0];
  const scoreNum = ev?.overall_score != null ? Math.round(Number(ev.overall_score)) : null;
  const tags = ev ? getExtractedTags(sub, ev) : [];
  const impBlock = ev ? formatImprovementsBlock(ev) : '';

  return (
    <div className="project-modal-overlay" onClick={onClose}>
      <div className="pmd-card" onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className="pmd-header">
          <div className="pmd-header__text">
            <h2 className="pmd-title">{template.title || 'Project'}</h2>
            <p className="pmd-meta">{summary}</p>
          </div>
          <button type="button" className="pmd-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Scrollable body */}
        <div className="pmd-body">

          {template.short_description ? (
            <p className="pmd-description">{template.short_description}</p>
          ) : null}

          {submissionReqs.length > 0 && (
            <section className="pmd-section">
              <h3 className="pmd-section__title">What to submit</h3>
              <ul className="pmd-req-list">
                {submissionReqs.map((line, idx) => (
                  <li key={idx} className="pmd-req-item">{friendlyRequirementLine(line)}</li>
                ))}
              </ul>
            </section>
          )}

          {hasInstructions && (
            <details className="pmd-instructions">
              <summary className="pmd-instructions__toggle">Read full instructions</summary>
              <div className="pmd-instructions__body">
                {template.business_problem && String(template.business_problem).trim() ? (
                  <div className="pmd-block">
                    <h4 className="pmd-block__title">Background</h4>
                    <p className="pmd-block__text">{template.business_problem}</p>
                  </div>
                ) : null}
                {inst.overview && String(inst.overview).trim() ? (
                  <div className="pmd-block">
                    <h4 className="pmd-block__title">Overview</h4>
                    <p className="pmd-block__text">{inst.overview}</p>
                  </div>
                ) : null}
                {steps.length > 0 ? (
                  <div className="pmd-block">
                    <h4 className="pmd-block__title">Steps</h4>
                    <ol className="pmd-block__list pmd-block__list--ordered">
                      {steps.map((line, idx) => <li key={idx}>{String(line)}</li>)}
                    </ol>
                  </div>
                ) : null}
                {deliverables.length > 0 ? (
                  <div className="pmd-block">
                    <h4 className="pmd-block__title">Deliverables</h4>
                    <ul className="pmd-block__list">
                      {deliverables.map((line, idx) => <li key={idx}>{String(line)}</li>)}
                    </ul>
                  </div>
                ) : null}
              </div>
            </details>
          )}

          <div className="pmd-score-row">
            <span className="pmd-score-label">Last score</span>
            <span className="pmd-score-value">
              {scoreNum != null && !Number.isNaN(scoreNum) ? `${scoreNum} / 100` : (assignment.latest_evaluation_score ?? '—')}
            </span>
          </div>

          {isEvaluating && (
            <div className="student-task-ai-evaluating" role="status" aria-live="polite">
              <span className="student-task-ai-evaluating__dot" aria-hidden />
              <span>🤖 AI Evaluator is analyzing your submission…</span>
            </div>
          )}

          {ev && (
            <div className="pmd-feedback">
              <strong className="pmd-feedback__title">AI feedback</strong>
              {ev.feedback_summary ? (
                <p className="pmd-feedback__text">{ev.feedback_summary}</p>
              ) : null}
              {impBlock ? (
                <>
                  <strong className="pmd-feedback__title" style={{ display: 'block', marginTop: '0.5rem' }}>Improvements</strong>
                  <p className="pmd-feedback__text">{impBlock}</p>
                </>
              ) : null}
              {tags.length > 0 && (
                <>
                  <strong className="pmd-feedback__title" style={{ display: 'block', marginTop: '0.35rem' }}>Topics detected</strong>
                  <div className="student-task-ai-tags">
                    {tags.map((tag, idx) => (
                      <span key={`${tag}-${idx}`} className="student-task-ai-tag">{tag}</span>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="pmd-footer">
          <button type="button" className="btn-outline-small" onClick={onClose}>Close</button>
          {canSubmit && (
            <button
              type="button"
              className="btn-submit"
              onClick={() => { onClose(); onOpenSubmit(assignment); }}
              disabled={isEvaluating}
              title={isEvaluating ? 'Wait for AI grading to finish.' : undefined}
            >
              {assignment.status === 'NEEDS_REVISION' ? 'Resubmit' : 'Submit'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Simple vertical list of project cards. Clicking a card opens the details popup. */
function TaskAssignmentList({ assignments, onOpenDetails, onAccept, onOpenSubmit }) {
  if (assignments.length === 0) return null;

  return (
    <div className="student-task-list">
      {assignments.map((assignment) => {
        const template = assignment.project_template || {};
        const summary = projectSummaryLine(template);
        return (
          <article
            key={assignment.id}
            className="student-task-card-simple"
            onClick={() => onOpenDetails(assignment)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onOpenDetails(assignment)}
          >
            <div className="student-task-card-simple__head">
              <div className="student-task-card-simple__titles">
                <span className="student-task-card-simple__name">{template.title || 'Project'}</span>
                <span className="student-task-card-simple__sub">{summary}</span>
              </div>
              <div className="student-task-card-simple__right" onClick={(e) => e.stopPropagation()}>
                <span className={`task-badge task-badge--soft ${statusBadgeClass(assignment.status)}`}>
                  {taskStatusLabel(assignment.status)}
                </span>
                {assignment.status === 'RECOMMENDED' && (
                  <button type="button" className="btn-primary-green student-task-card-simple__btn" onClick={() => onAccept(assignment.id)}>
                    Add to list
                  </button>
                )}
                {assignment.status === 'SUBMITTED' && (
                  <button type="button" className="btn-outline-primary student-task-card-simple__btn" disabled>
                    Evaluating…
                  </button>
                )}
                {['IN_PROGRESS', 'NEEDS_REVISION'].includes(assignment.status) && (
                  <button
                    type="button"
                    className="btn-submit student-task-card-simple__btn"
                    onClick={() => onOpenSubmit(assignment)}
                    disabled={isAiEvaluationPending(assignment)}
                    title={isAiEvaluationPending(assignment) ? 'Wait for AI grading to finish.' : undefined}
                  >
                    {assignment.status === 'NEEDS_REVISION' ? 'Resubmit' : 'Submit'}
                  </button>
                )}
              </div>
            </div>
          </article>
        );
      })}
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
  const [detailsTarget, setDetailsTarget] = useState(null);
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
          inProgress: list.filter((item) => ['IN_PROGRESS', 'NEEDS_REVISION', 'SUBMITTED', 'PENDING_MENTOR_REVIEW'].includes(item.status)).length,
        });
      }
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not load your projects.');
    } finally {
      setLoading(false);
    }
  }, [onStatsChange]);

  const assignmentsRef = useRef([]);
  useEffect(() => {
    assignmentsRef.current = assignments;
  }, [assignments]);

  const pendingAiEvaluation = useMemo(
    () => assignments.some(
      (a) => a.status === 'SUBMITTED' && a.latest_submission?.status === 'SUBMITTED',
    ),
    [assignments],
  );

  useEffect(() => {
    if (!pendingAiEvaluation) return undefined;

    let stopped = false;

    const pollOnce = async () => {
      if (stopped) return;
      const rows = assignmentsRef.current.filter(
        (a) => a.status === 'SUBMITTED' && a.latest_submission?.status === 'SUBMITTED',
      );
      if (rows.length === 0) return;

      for (let i = 0; i < rows.length; i += 1) {
        const sid = rows[i].latest_submission?.id;
        if (!sid) continue;
        try {
          // eslint-disable-next-line no-await-in-loop
          const { data } = await studentApi.getSubmissionFeedback(sid);
          if (stopped) return;
          if (data.status !== 'SUBMITTED') {
            await loadAssignments();
            return;
          }
        } catch (err) {
          if (!stopped) {
            // eslint-disable-next-line no-console
            console.warn('Submission feedback poll failed:', err);
          }
        }
      }
    };

    pollOnce();
    const timer = setInterval(pollOnce, 5000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [pendingAiEvaluation, loadAssignments]);

  const refreshRecommendations = useCallback(async () => {
    setRefreshingRecommendations(true);
    try {
      await studentApi.getRecommendedProjects();
      await loadAssignments();
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not refresh suggestions.');
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

  const openDetails = useCallback((assignment) => setDetailsTarget(assignment), []);
  const closeDetails = useCallback(() => setDetailsTarget(null), []);

  const sortByAssignedAtDesc = (a, b) => {
    const ta = a.assigned_at ? new Date(a.assigned_at).getTime() : 0;
    const tb = b.assigned_at ? new Date(b.assigned_at).getTime() : 0;
    return tb - ta;
  };

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
    if (activeTab === 'active') {
      return assignments.filter((item) => ['IN_PROGRESS', 'SUBMITTED', 'NEEDS_REVISION', 'PENDING_MENTOR_REVIEW'].includes(item.status));
    }
    return assignments.filter((item) => item.status === 'COMPLETED');
  }, [activeTab, assignments, recommendedFeeds]);

  const acceptProject = async (assignmentId) => {
    try {
      await studentApi.acceptProject(assignmentId);
      await loadAssignments();
      setActiveTab('active');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not add this project.');
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
  const modalHandInLabel = handInTypeLabel(modalSt);
  const modalLevelLabel = levelLabel(submissionTarget?.project_template?.complexity);

  if (!assessmentPassed) {
    return (
      <div className="dashboard-section">
        <h1>Projects</h1>
        <p className="section-desc">Finish the skill check first. Then we unlock projects matched to you.</p>
        <div className="tasks-locked-block">
          <p className="student-task-muted">Your list will show up here after the assessment.</p>
          <button type="button" onClick={onStartAssessment} className="btn-outline-primary">Go to skill check</button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-section student-tasks-root">
      <div className="student-tasks-toolbar student-tasks-toolbar--simple">
        <div className="student-tasks-toolbar__text">
          <h1>Projects</h1>
          <p className="section-desc">Tap a card to read the brief. Use <strong>Submit</strong> when you are ready.</p>
        </div>
        <button
          type="button"
          className="btn-recommend-projects"
          onClick={refreshRecommendations}
          disabled={refreshingRecommendations}
        >
          {refreshingRecommendations ? 'Finding projects…' : 'Recommend projects'}
        </button>
      </div>

      {error && <p className="student-tasks-error" role="alert">{error}</p>}

      {progress && (
        <div className="student-stats-strip">
          <div className="student-stats-strip__item">
            <span className="student-stats-strip__value">{progress.completed_projects}</span>
            <span className="student-stats-strip__label">Done</span>
          </div>
          <div className="student-stats-strip__item">
            <span className="student-stats-strip__value">{progress.average_score}</span>
            <span className="student-stats-strip__label">Avg. score</span>
          </div>
          <div className="student-stats-strip__item">
            <span className="student-stats-strip__value">{levelLabel(progress.current_complexity_band)}</span>
            <span className="student-stats-strip__label">Level</span>
          </div>
          <div className="student-stats-strip__item">
            <span className="student-stats-strip__value">{progress.strongest_domain?.name || '—'}</span>
            <span className="student-stats-strip__label">Strong topic</span>
          </div>
        </div>
      )}

      <div className="student-tasks-tabs" role="tablist" aria-label="Project lists">
        <button type="button" role="tab" aria-selected={activeTab === 'recommended'} className={activeTab === 'recommended' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('recommended')}>Suggested</button>
        <button type="button" role="tab" aria-selected={activeTab === 'active'} className={activeTab === 'active' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('active')}>In progress</button>
        <button type="button" role="tab" aria-selected={activeTab === 'completed'} className={activeTab === 'completed' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('completed')}>Done</button>
      </div>

      {loading ? (
        <p className="student-task-muted">Loading…</p>
      ) : activeTab === 'recommended'
        && recommendedFeeds.contentBasedRows.length === 0
        && recommendedFeeds.collaborativeRows.length === 0 ? (
        <div className="info-card info-card--plain">
          <p>No suggestions yet. Tap <strong>Recommend projects</strong> or finish a project first.</p>
        </div>
        ) : activeTab !== 'recommended' && filteredAssignments.length === 0 ? (
          <div className="info-card info-card--plain">
            <p>{activeTab === 'active' ? 'Nothing in progress right now.' : 'No finished projects yet.'}</p>
          </div>
        ) : activeTab === 'recommended' ? (
          <div className="student-recommended-feeds">
            {recommendedFeeds.contentBasedRows.length > 0 && (
              <section className="student-feed-section" aria-labelledby="feed-for-you">
                <h2 id="feed-for-you" className="student-feed-section__title">For you</h2>
                <p className="student-feed-section__hint">Based on your assessment and progress.</p>
                <TaskAssignmentList
                  assignments={recommendedFeeds.contentBasedRows}
                  onOpenDetails={openDetails}
                  onAccept={acceptProject}
                  onOpenSubmit={openSubmitModal}
                />
              </section>
            )}
            {recommendedFeeds.collaborativeRows.length > 0 && (
              <section className="student-feed-section" aria-labelledby="feed-popular">
                <h2 id="feed-popular" className="student-feed-section__title">Popular with similar students</h2>
                <p className="student-feed-section__hint">Projects others at your stage often take next.</p>
                <TaskAssignmentList
                  assignments={recommendedFeeds.collaborativeRows}
                  onOpenDetails={openDetails}
                  onAccept={acceptProject}
                  onOpenSubmit={openSubmitModal}
                />
              </section>
            )}
          </div>
        ) : (
          <TaskAssignmentList
            assignments={filteredAssignments}
            onOpenDetails={openDetails}
            onAccept={acceptProject}
            onOpenSubmit={openSubmitModal}
          />
        )}

      {detailsTarget && (
        <ProjectDetailsModal
          assignment={detailsTarget}
          onClose={closeDetails}
          onOpenSubmit={openSubmitModal}
        />
      )}

      {submissionTarget && (
        <div className="project-modal-overlay" onClick={closeSubmitModal}>
          <div className="project-modal-card project-modal-card--simple" onClick={(event) => event.stopPropagation()}>
            <h2 className="project-modal-card__title">Submit your work</h2>
            <p className="project-modal-card__subtitle">{submissionTarget.project_template?.title}</p>
            <p className="project-modal-card__meta">
              {modalHandInLabel}
              {modalLevelLabel ? ` · ${modalLevelLabel}` : ''}
            </p>
            <form onSubmit={submitProject} className="project-form-grid project-form-grid--simple">
              <label className="project-form-span-2">
                <span className="project-form-label">Upload file</span>
                <span className="student-field-hint">
                  {modalSt === 'CODE'
                    ? 'Upload one ZIP file only (max 15 MB).'
                    : 'Upload one file (PDF, Word, Excel, text, image, or ZIP) — max 15 MB.'}
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  required
                  accept=".zip,.pdf,.doc,.docx,.xlsx,.xls,.txt,.png,.jpg,.jpeg,.gif,.webp"
                />
              </label>
              <label className="project-form-span-2">
                <span className="project-form-label">Short summary</span>
                <span className="student-field-hint">A few sentences on what you built (optional).</span>
                <input
                  value={submissionForm.submission_text}
                  onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submission_text: e.target.value }))}
                  placeholder="What did you complete?"
                />
              </label>
              <label className="project-form-span-2">
                <span className="project-form-label">Notes for reviewer</span>
                <span className="student-field-hint">Optional.</span>
                <textarea rows={2} value={submissionForm.notes} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span className="project-form-label">Important files or paths in your ZIP</span>
                <span className="student-field-hint">One per line (optional), e.g. src/app.py</span>
                <textarea rows={3} value={submissionForm.submitted_files} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submitted_files: e.target.value }))} />
              </label>
              <p className="project-form-note project-form-span-2">
                We score your work in the background. Refresh this page in a few seconds to see your result.
              </p>
              <div className="project-form-actions project-form-span-2">
                <button type="submit" className="btn-primary-green" disabled={submitting}>
                  {submitting ? 'Sending…' : 'Send for review'}
                </button>
                <button type="button" className="btn-outline-small" onClick={closeSubmitModal}>
                  Close
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
