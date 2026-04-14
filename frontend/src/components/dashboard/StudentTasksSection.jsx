import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { studentApi } from '../../api/student.api';
import {
  buildProjectSubmissionPayload,
  formatSubmissionError,
  isFileSubmissionType,
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
  repository_url: '',
  artifact_url: '',
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

/** What to do + full brief (shown under each project card when expanded). */
function TaskExpandedDetails({ assignment }) {
  const template = assignment.project_template || {};
  const inst = template.instruction || {};
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
    <div className="student-task-expand student-task-expand--simple">
      {template.short_description ? (
        <p className="student-task-expand__lead">{template.short_description}</p>
      ) : null}

      {assignment.recommendation_reason ? (
        <div className="student-task-callout">
          <span className="student-task-callout__label">Why we suggested this</span>
          <p className="student-task-callout__text">{assignment.recommendation_reason}</p>
        </div>
      ) : null}

      {(template.tags || []).length > 0 ? (
        <div className="student-task-tags">
          {(template.tags || []).slice(0, 10).map((tag) => (
            <span key={tag} className="student-task-tag">{tag}</span>
          ))}
        </div>
      ) : null}

      {submissionReqs.length > 0 && (
        <section className="student-task-requirements" aria-labelledby="handin-heading">
          <h3 id="handin-heading" className="student-task-requirements__title">What to hand in</h3>
          <ul className="student-task-requirements__list">
            {submissionReqs.map((line, idx) => (
              <li key={idx} className="student-task-requirements__item">{friendlyRequirementLine(line)}</li>
            ))}
          </ul>
        </section>
      )}

      {hasMoreBrief && (
        <details className="student-task-details">
          <summary className="student-task-details__summary">Read full instructions</summary>
          <div className="student-task-details__body">
            {template.business_problem && String(template.business_problem).trim() ? (
              <section className="student-task-block">
                <h3 className="student-task-block__title">Background</h3>
                <p className="student-task-block__text">{template.business_problem}</p>
              </section>
            ) : null}
            {inst.overview && String(inst.overview).trim() ? (
              <section className="student-task-block">
                <h3 className="student-task-block__title">Overview</h3>
                <p className="student-task-block__text">{inst.overview}</p>
              </section>
            ) : null}
            {steps.length > 0 ? (
              <section className="student-task-block">
                <h3 className="student-task-block__title">Steps</h3>
                <ol className="student-task-block__list student-task-block__list--ordered">
                  {steps.map((line, idx) => (
                    <li key={idx}>{String(line)}</li>
                  ))}
                </ol>
              </section>
            ) : null}
            {deliverables.length > 0 ? (
              <section className="student-task-block">
                <h3 className="student-task-block__title">Deliverables</h3>
                <ul className="student-task-block__list">
                  {deliverables.map((line, idx) => (
                    <li key={idx}>{String(line)}</li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        </details>
      )}

      <div className="student-task-meta-row">
        <div>
          <span className="student-task-meta-row__label">Last score</span>
          <span className="student-task-meta-row__value">{assignment.latest_evaluation_score ?? '—'}</span>
        </div>
        <div>
          <span className="student-task-meta-row__label">Skills to have first</span>
          <span className="student-task-meta-row__value">
            {(template.prerequisite_skills || []).join(', ') || '—'}
          </span>
        </div>
      </div>

      {isAiEvaluationPending(assignment) && (
        <div className="student-task-ai-evaluating" role="status" aria-live="polite">
          <span className="student-task-ai-evaluating__dot" aria-hidden />
          <span>🤖 AI Evaluator is analyzing your submission…</span>
        </div>
      )}

      {assignment.latest_submission?.evaluations?.[0] && (
        <div className="student-task-feedback">
          <strong className="student-task-feedback__title">AI feedback</strong>
          {(() => {
            const sub = assignment.latest_submission;
            const ev = sub.evaluations[0];
            const scoreNum = ev.overall_score != null ? Math.round(Number(ev.overall_score)) : null;
            const tags = getExtractedTags(sub, ev);
            const impBlock = formatImprovementsBlock(ev);
            return (
              <>
                {scoreNum != null && !Number.isNaN(scoreNum) && (
                  <p className="student-task-ai-score">
                    {scoreNum}
                    <span> / 100</span>
                  </p>
                )}
                {ev.feedback_summary ? (
                  <p className="student-task-feedback__text">{ev.feedback_summary}</p>
                ) : null}
                {impBlock ? (
                  <div>
                    <span className="student-task-feedback__title" style={{ display: 'block', marginTop: '0.5rem' }}>Improvements</span>
                    <p className="student-task-ai-improvements">{impBlock}</p>
                  </div>
                ) : null}
                {tags.length > 0 && (
                  <div>
                    <span className="student-task-feedback__title" style={{ display: 'block', marginTop: '0.35rem' }}>Topics detected</span>
                    <div className="student-task-ai-tags">
                      {tags.map((tag, idx) => (
                        <span key={`${tag}-${idx}`} className="student-task-ai-tag">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

/** Simple vertical list of project cards (replaces dense table). */
function TaskAssignmentList({
  assignments,
  expandedId,
  onToggleRow,
  onAccept,
  onOpenSubmit,
}) {
  if (assignments.length === 0) return null;

  return (
    <div className="student-task-list">
      {assignments.map((assignment) => {
        const template = assignment.project_template || {};
        const expanded = expandedId === assignment.id;
        const summary = projectSummaryLine(template);
        return (
          <article key={assignment.id} className={`student-task-card-simple${expanded ? ' is-open' : ''}`}>
            <div className="student-task-card-simple__head">
              <button
                type="button"
                className="student-task-card-simple__toggle"
                onClick={() => onToggleRow(assignment.id)}
                aria-expanded={expanded}
              >
                <span className="student-task-card-simple__chev" aria-hidden>{expanded ? '▼' : '▶'}</span>
                <span className="student-task-card-simple__titles">
                  <span className="student-task-card-simple__name">{template.title || 'Project'}</span>
                  <span className="student-task-card-simple__sub">{summary}</span>
                </span>
              </button>
              <div className="student-task-card-simple__badges" onClick={(e) => e.stopPropagation()}>
                <span className={`task-badge task-badge--soft ${statusBadgeClass(assignment.status)}`}>
                  {taskStatusLabel(assignment.status)}
                </span>
              </div>
            </div>
            <div className="student-task-card-simple__actions" onClick={(e) => e.stopPropagation()}>
              {assignment.status === 'RECOMMENDED' && (
                <button type="button" className="btn-primary-green student-task-card-simple__btn" onClick={() => onAccept(assignment.id)}>
                  Add to my list
                </button>
              )}
              {assignment.status === 'SUBMITTED' && (
                <button type="button" className="btn-outline-primary student-task-card-simple__btn" disabled>
                  🤖 AI Evaluator is analyzing…
                </button>
              )}
              {['IN_PROGRESS', 'NEEDS_REVISION'].includes(assignment.status) && (
                <button
                  type="button"
                  className="btn-primary student-task-card-simple__btn"
                  onClick={() => onOpenSubmit(assignment)}
                  disabled={isAiEvaluationPending(assignment)}
                  title={isAiEvaluationPending(assignment) ? 'Wait for AI grading to finish before resubmitting.' : undefined}
                >
                  {assignment.status === 'NEEDS_REVISION' ? 'Hand in again' : 'Hand in work'}
                </button>
              )}
            </div>
            {expanded ? (
              <div className="student-task-card-simple__body">
                <TaskExpandedDetails assignment={assignment} />
              </div>
            ) : null}
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

  useEffect(() => {
    setExpandedAssignmentId(null);
  }, [activeTab]);

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
  const modalIsCode = Boolean(submissionTarget) && modalSt === 'CODE';
  const modalIsFile = Boolean(submissionTarget) && isFileSubmissionType(modalSt);
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
          <p className="section-desc">Tap a card to read the brief. Use <strong>Hand in work</strong> when you are ready.</p>
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
                  expandedId={expandedAssignmentId}
                  onToggleRow={toggleRow}
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
                  expandedId={expandedAssignmentId}
                  onToggleRow={toggleRow}
                  onAccept={acceptProject}
                  onOpenSubmit={openSubmitModal}
                />
              </section>
            )}
          </div>
        ) : (
          <TaskAssignmentList
            assignments={filteredAssignments}
            expandedId={expandedAssignmentId}
            onToggleRow={toggleRow}
            onAccept={acceptProject}
            onOpenSubmit={openSubmitModal}
          />
        )}

      {submissionTarget && (
        <div className="project-modal-overlay" onClick={closeSubmitModal}>
          <div className="project-modal-card project-modal-card--simple" onClick={(event) => event.stopPropagation()}>
            <h2 className="project-modal-card__title">Hand in your work</h2>
            <p className="project-modal-card__subtitle">{submissionTarget.project_template?.title}</p>
            <p className="project-modal-card__meta">
              {modalHandInLabel}
              {modalLevelLabel ? ` · ${modalLevelLabel}` : ''}
            </p>
            <form onSubmit={submitProject} className="project-form-grid project-form-grid--simple">
              {modalIsCode && (
                <label className="project-form-span-2">
                  <span className="project-form-label">GitHub link</span>
                  <span className="student-field-hint">Paste a link to your repo or a single file on GitHub.</span>
                  <input
                    required
                    type="text"
                    inputMode="url"
                    autoComplete="url"
                    placeholder="https://github.com/you/project"
                    value={submissionForm.repository_url}
                    onChange={(e) => setSubmissionForm((prev) => ({ ...prev, repository_url: e.target.value }))}
                  />
                </label>
              )}
              {modalIsFile && (
                <label className="project-form-span-2">
                  <span className="project-form-label">Your file</span>
                  <span className="student-field-hint">PDF, Word, Excel, text, or image — max 15 MB.</span>
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
                  <span className="project-form-label">GitHub link</span>
                  <input value={submissionForm.repository_url} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, repository_url: e.target.value }))} />
                </label>
              )}
              <label className="project-form-span-2">
                <span className="project-form-label">Demo or extra link</span>
                <span className="student-field-hint">Figma, Drive, live site — optional.</span>
                <input
                  value={submissionForm.artifact_url}
                  onChange={(e) => setSubmissionForm((prev) => ({ ...prev, artifact_url: e.target.value }))}
                  placeholder="https://…"
                />
              </label>
              <label className="project-form-span-2">
                <span className="project-form-label">Short summary</span>
                <span className="student-field-hint">A few sentences on what you built {modalIsFile ? '(optional)' : ''}.</span>
                <textarea rows={4} value={submissionForm.submission_text} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submission_text: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span className="project-form-label">Notes for reviewer</span>
                <span className="student-field-hint">Optional.</span>
                <textarea rows={2} value={submissionForm.notes} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>
              {(modalIsCode || (!modalIsCode && !modalIsFile)) && (
                <label className="project-form-span-2">
                  <span className="project-form-label">Important paths in your repo</span>
                  <span className="student-field-hint">One per line, e.g. src/app.py — optional, helps the review.</span>
                  <textarea rows={3} value={submissionForm.submitted_files} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submitted_files: e.target.value }))} />
                </label>
              )}
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
