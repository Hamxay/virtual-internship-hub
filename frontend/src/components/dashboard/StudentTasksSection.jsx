import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { studentApi } from '../../api/student.api';
import { buildProjectSubmissionPayload } from '../../services/student.service';

const EMPTY_SUBMISSION_FORM = {
  repository_url: '',
  artifact_url: '',
  submission_text: '',
  notes: '',
  submitted_files: '',
};

function TaskCard({ assignment, onAccept, onOpenSubmit }) {
  const template = assignment.project_template || {};
  const latestEvaluation = assignment.latest_submission?.evaluations?.[0];
  return (
    <div className="student-task-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start' }}>
        <div>
          <h3 style={{ margin: '0 0 0.35rem 0' }}>{template.title}</h3>
          <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>
            {template.domain?.name} • {template.complexity} • {template.submission_type} • {template.estimated_hours}h
          </p>
        </div>
        <span className={`task-badge ${assignment.status === 'COMPLETED' ? 'complete' : assignment.status === 'NEEDS_REVISION' ? 'danger' : 'beginner'}`}>
          {assignment.status.replaceAll('_', ' ')}
        </span>
      </div>
      <p style={{ color: '#334155', margin: '0.75rem 0' }}>{template.short_description}</p>
      {assignment.recommendation_reason && (
        <p style={{ margin: '0 0 0.75rem 0', color: '#0f766e', fontSize: '0.875rem' }}>
          <strong>Why this project:</strong> {assignment.recommendation_reason}
        </p>
      )}
      <div className="project-chip-row">
        {(template.tags || []).slice(0, 4).map((tag) => <span key={tag} className="project-chip">{tag}</span>)}
      </div>
      <div className="project-meta-grid" style={{ marginTop: '0.75rem' }}>
        <div>
          <strong>Deliverables</strong>
          <div>{(template.instruction?.deliverables || []).slice(0, 3).join(' • ') || 'Check the full instructions'}</div>
        </div>
        <div>
          <strong>Last Score</strong>
          <div>{assignment.latest_evaluation_score ?? 'Not evaluated yet'}</div>
        </div>
      </div>
      {latestEvaluation && (
        <div className="task-feedback-box">
          <strong>AI Feedback</strong>
          <p style={{ margin: '0.35rem 0 0 0' }}>{latestEvaluation.feedback_summary}</p>
          {Array.isArray(latestEvaluation.improvements) && latestEvaluation.improvements.length > 0 && (
            <p style={{ margin: '0.35rem 0 0 0', color: '#92400e' }}>
              Improve: {latestEvaluation.improvements.slice(0, 2).join(' • ')}
            </p>
          )}
        </div>
      )}
      <div className="project-form-actions" style={{ marginTop: '1rem' }}>
        {assignment.status === 'RECOMMENDED' && (
          <button type="button" className="btn-primary-green" onClick={() => onAccept(assignment.id)}>
            Accept Project
          </button>
        )}
        {['IN_PROGRESS', 'NEEDS_REVISION'].includes(assignment.status) && (
          <button type="button" className="btn-primary" onClick={() => onOpenSubmit(assignment)}>
            {assignment.status === 'NEEDS_REVISION' ? 'Resubmit Work' : 'Submit Work'}
          </button>
        )}
      </div>
    </div>
  );
}

export default function StudentTasksSection({ assessmentPassed, onStartAssessment, onStatsChange }) {
  const [recommended, setRecommended] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshingRecommendations, setRefreshingRecommendations] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('recommended');
  const [submissionTarget, setSubmissionTarget] = useState(null);
  const [submissionForm, setSubmissionForm] = useState(EMPTY_SUBMISSION_FORM);
  const [submitting, setSubmitting] = useState(false);

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

  const loadRecommended = useCallback(async () => {
    setRefreshingRecommendations(true);
    try {
      const response = await studentApi.getRecommendedProjects();
      const list = Array.isArray(response?.data) ? response.data : (response?.data?.results || []);
      setRecommended(list);
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load recommendations.');
    } finally {
      setRefreshingRecommendations(false);
    }
  }, []);

  useEffect(() => {
    if (!assessmentPassed) {
      setLoading(false);
      return;
    }
    loadAssignments();
    loadRecommended();
  }, [assessmentPassed, loadAssignments, loadRecommended]);

  const filteredAssignments = useMemo(() => {
    if (activeTab === 'recommended') return recommended;
    if (activeTab === 'active') return assignments.filter((item) => ['IN_PROGRESS', 'SUBMITTED', 'NEEDS_REVISION'].includes(item.status));
    return assignments.filter((item) => item.status === 'COMPLETED');
  }, [activeTab, assignments, recommended]);

  const acceptProject = async (assignmentId) => {
    try {
      await studentApi.acceptProject(assignmentId);
      await Promise.all([loadAssignments(), loadRecommended()]);
      setActiveTab('active');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not accept project.');
    }
  };

  const submitProject = async (event) => {
    event.preventDefault();
    if (!submissionTarget) return;
    setSubmitting(true);
    try {
      await studentApi.submitProject(submissionTarget.id, buildProjectSubmissionPayload(submissionForm));
      setSubmissionTarget(null);
      setSubmissionForm(EMPTY_SUBMISSION_FORM);
      await Promise.all([loadAssignments(), loadRecommended()]);
      setActiveTab('active');
    } catch (err) {
      setError(err.response?.data?.detail || JSON.stringify(err.response?.data || {}) || err.message);
    } finally {
      setSubmitting(false);
    }
  };

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
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start', marginBottom: '1rem' }}>
        <div>
          <h1>My Tasks</h1>
          <p className="section-desc">Recommended, active, and completed projects based on your profile and progress.</p>
        </div>
        <button type="button" className="btn-outline-small" onClick={loadRecommended} disabled={refreshingRecommendations}>
          {refreshingRecommendations ? 'Refreshing...' : 'Refresh Recommendations'}
        </button>
      </div>

      {error && <p style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</p>}

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

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button type="button" className={activeTab === 'recommended' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('recommended')}>Recommended</button>
        <button type="button" className={activeTab === 'active' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('active')}>Active</button>
        <button type="button" className={activeTab === 'completed' ? 'tab-btn active' : 'tab-btn'} onClick={() => setActiveTab('completed')}>Completed</button>
      </div>

      {loading ? (
        <p style={{ color: '#6b7280' }}>Loading tasks...</p>
      ) : filteredAssignments.length === 0 ? (
        <div className="info-card">
          <p>
            {activeTab === 'recommended'
              ? 'No recommendations yet. Refresh recommendations or complete a project to improve personalization.'
              : activeTab === 'active'
                ? 'No active assignments yet.'
                : 'No completed projects yet.'}
          </p>
        </div>
      ) : (
        <div className="template-list-grid">
          {filteredAssignments.map((assignment) => (
            <TaskCard
              key={assignment.id}
              assignment={assignment}
              onAccept={acceptProject}
              onOpenSubmit={(target) => {
                setSubmissionTarget(target);
                setSubmissionForm(EMPTY_SUBMISSION_FORM);
              }}
            />
          ))}
        </div>
      )}

      {submissionTarget && (
        <div className="project-modal-overlay" onClick={() => setSubmissionTarget(null)}>
          <div className="project-modal-card" onClick={(event) => event.stopPropagation()}>
            <h2 style={{ marginTop: 0 }}>Submit Project</h2>
            <p style={{ color: '#6b7280', marginTop: 0 }}>{submissionTarget.project_template?.title}</p>
            <form onSubmit={submitProject} className="project-form-grid">
              <label className="project-form-span-2">
                <span>Repository URL</span>
                <input value={submissionForm.repository_url} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, repository_url: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Artifact URL</span>
                <input value={submissionForm.artifact_url} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, artifact_url: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Submission Summary</span>
                <textarea rows={5} value={submissionForm.submission_text} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submission_text: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Notes</span>
                <textarea rows={3} value={submissionForm.notes} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, notes: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Submitted Files (one per line)</span>
                <textarea rows={3} value={submissionForm.submitted_files} onChange={(e) => setSubmissionForm((prev) => ({ ...prev, submitted_files: e.target.value }))} />
              </label>
              <div className="project-form-actions project-form-span-2">
                <button type="submit" className="btn-primary-green" disabled={submitting}>
                  {submitting ? 'Submitting...' : 'Submit For AI Review'}
                </button>
                <button type="button" className="btn-outline-small" onClick={() => setSubmissionTarget(null)}>
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
