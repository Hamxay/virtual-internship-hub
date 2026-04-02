import React, { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../../api/admin.api';
import { useDomains } from '../../hooks/useDomains';
import { buildProjectAssignPayload, buildProjectTemplatePayload } from '../../services/admin.service';

const EMPTY_TEMPLATE_FORM = {
  domain_id: '',
  title: '',
  short_description: '',
  business_problem: '',
  complexity: 'BEGINNER',
  submission_type: 'CODE',
  estimated_hours: 8,
  tags: '',
  prerequisite_skills: '',
  expected_keywords: '',
  instruction_overview: '',
  steps: '',
  deliverables: '',
  submission_requirements: '',
  starter_resources: '',
  evaluation_notes: '',
  passing_score: 70,
  plagiarism_threshold: 75,
  grammar_weight: 15,
  correctness_weight: 40,
  originality_weight: 25,
  communication_weight: 15,
  quality_weight: 20,
  allow_auto_accept: true,
  active: true,
};

const EMPTY_ASSIGN_FORM = {
  student_id: '',
  project_template_id: '',
  due_date: '',
  recommendation_reason: '',
};

function joinLines(items) {
  return Array.isArray(items) ? items.join('\n') : '';
}

function mapTemplateToForm(template) {
  const criteria = Array.isArray(template?.rubric?.criteria) ? template.rubric.criteria : [];
  const byKey = Object.fromEntries(criteria.map((item) => [item.key, item]));
  return {
    domain_id: template?.domain?.id || '',
    title: template?.title || '',
    short_description: template?.short_description || '',
    business_problem: template?.business_problem || '',
    complexity: template?.complexity || 'BEGINNER',
    submission_type: template?.submission_type || 'CODE',
    estimated_hours: template?.estimated_hours || 8,
    tags: joinLines(template?.tags),
    prerequisite_skills: joinLines(template?.prerequisite_skills),
    expected_keywords: joinLines(template?.expected_keywords),
    instruction_overview: template?.instruction?.overview || '',
    steps: joinLines(template?.instruction?.steps),
    deliverables: joinLines(template?.instruction?.deliverables),
    submission_requirements: joinLines(template?.instruction?.submission_requirements),
    starter_resources: joinLines(template?.instruction?.starter_resources),
    evaluation_notes: template?.instruction?.evaluation_notes || '',
    passing_score: template?.rubric?.passing_score || 70,
    plagiarism_threshold: template?.rubric?.plagiarism_threshold || 75,
    grammar_weight: template?.rubric?.grammar_weight || 15,
    correctness_weight: byKey.correctness?.weight || 40,
    originality_weight: byKey.originality?.weight || 25,
    communication_weight: byKey.communication?.weight || 15,
    quality_weight: byKey.quality?.weight || 20,
    allow_auto_accept: Boolean(template?.rubric?.allow_auto_accept ?? true),
    active: Boolean(template?.active ?? true),
  };
}

function MetricCard({ label, value }) {
  return (
    <div className="project-metric-card">
      <div className="project-metric-label">{label}</div>
      <div className="project-metric-value">{value}</div>
    </div>
  );
}

function TemplateListCard({ template, onEdit, onDelete }) {
  const latestCriteria = Array.isArray(template?.rubric?.criteria) ? template.rubric.criteria : [];
  return (
    <div className="template-list-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start' }}>
        <div>
          <h3 style={{ margin: '0 0 0.4rem 0', fontSize: '1rem' }}>{template.title}</h3>
          <p style={{ margin: 0, color: '#6b7280', fontSize: '0.875rem' }}>
            {template.domain?.name} • {template.complexity} • {template.submission_type} • {template.estimated_hours}h
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" className="btn-outline-small" onClick={() => onEdit(template)}>Edit</button>
          <button type="button" className="btn-outline-small danger" onClick={() => onDelete(template)}>Delete</button>
        </div>
      </div>
      <p style={{ margin: '0.75rem 0', color: '#374151' }}>{template.short_description}</p>
      <div className="project-chip-row">
        {(template.tags || []).slice(0, 4).map((tag) => <span key={tag} className="project-chip">{tag}</span>)}
      </div>
      <div className="project-meta-grid">
        <div>
          <strong>Deliverables</strong>
          <div>{(template.instruction?.deliverables || []).slice(0, 3).join(' • ') || 'No deliverables yet'}</div>
        </div>
        <div>
          <strong>Rubric</strong>
          <div>{latestCriteria.map((item) => `${item.label} ${item.weight}%`).join(' • ') || 'Default rubric'}</div>
        </div>
      </div>
    </div>
  );
}

export default function AdminProjectsSection() {
  const { domains } = useDomains();
  const [templates, setTemplates] = useState([]);
  const [students, setStudents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [pendingSubmissions, setPendingSubmissions] = useState([]);
  const [templateForm, setTemplateForm] = useState(EMPTY_TEMPLATE_FORM);
  const [assignForm, setAssignForm] = useState(EMPTY_ASSIGN_FORM);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [savingAssignment, setSavingAssignment] = useState(false);
  const [error, setError] = useState('');

  const loadAll = async () => {
    setLoading(true);
    try {
      const [templateRes, studentRes, summaryRes, pendingRes] = await Promise.all([
        adminApi.getProjectTemplates(),
        adminApi.getStudents(),
        adminApi.getEvaluationSummary(),
        adminApi.getPendingSubmissions(),
      ]);
      const templateData = templateRes?.data;
      setTemplates(Array.isArray(templateData) ? templateData : (templateData?.results || []));
      const studentData = studentRes?.data;
      setStudents(Array.isArray(studentData) ? studentData : (studentData?.results || []));
      setSummary(summaryRes?.data || null);
      const pendingData = pendingRes?.data;
      setPendingSubmissions(Array.isArray(pendingData) ? pendingData : (pendingData?.results || []));
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load project data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const domainOptions = Array.isArray(domains) ? domains : [];
  const templateOptions = useMemo(() => templates.map((item) => ({ id: item.id, title: item.title })), [templates]);

  const handleTemplateSave = async (event) => {
    event.preventDefault();
    setSavingTemplate(true);
    setError('');
    try {
      const payload = buildProjectTemplatePayload(templateForm);
      if (editingTemplate?.id) {
        await adminApi.updateProjectTemplate(editingTemplate.id, payload);
      } else {
        await adminApi.createProjectTemplate(payload);
      }
      setTemplateForm(EMPTY_TEMPLATE_FORM);
      setEditingTemplate(null);
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || JSON.stringify(err.response?.data || {}) || err.message);
    } finally {
      setSavingTemplate(false);
    }
  };

  const handleAssign = async (event) => {
    event.preventDefault();
    setSavingAssignment(true);
    setError('');
    try {
      await adminApi.assignProject(buildProjectAssignPayload(assignForm));
      setAssignForm(EMPTY_ASSIGN_FORM);
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || JSON.stringify(err.response?.data || {}) || err.message);
    } finally {
      setSavingAssignment(false);
    }
  };

  const handleDelete = async (template) => {
    if (!window.confirm(`Delete template "${template.title}"?`)) return;
    try {
      await adminApi.deleteProjectTemplate(template.id);
      if (editingTemplate?.id === template.id) {
        setEditingTemplate(null);
        setTemplateForm(EMPTY_TEMPLATE_FORM);
      }
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Delete failed.');
    }
  };

  return (
    <div className="dashboard-section">
      <h1>Project Templates</h1>
      <p className="section-desc">Create domain projects, assign tasks, and review AI-evaluated submissions.</p>
      {error && <p style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</p>}

      <div className="project-metric-grid">
        <MetricCard label="Templates" value={summary?.template_count ?? templates.length} />
        <MetricCard label="Assignments" value={summary?.assignment_count ?? 0} />
        <MetricCard label="Flagged" value={summary?.flagged_submissions ?? 0} />
        <MetricCard label="Avg Completed Score" value={summary?.average_completed_score ?? 0} />
      </div>

      <div className="project-two-col">
        <div className="project-panel">
          <h2>{editingTemplate ? 'Edit Template' : 'Create Template'}</h2>
          <form onSubmit={handleTemplateSave} className="project-form-grid">
            <label>
              <span>Domain</span>
              <select value={templateForm.domain_id} onChange={(e) => setTemplateForm((prev) => ({ ...prev, domain_id: e.target.value }))} required>
                <option value="">Select domain</option>
                {domainOptions.map((domain) => <option key={domain.id} value={domain.id}>{domain.name}</option>)}
              </select>
            </label>
            <label>
              <span>Title</span>
              <input value={templateForm.title} onChange={(e) => setTemplateForm((prev) => ({ ...prev, title: e.target.value }))} required />
            </label>
            <label>
              <span>Complexity</span>
              <select value={templateForm.complexity} onChange={(e) => setTemplateForm((prev) => ({ ...prev, complexity: e.target.value }))}>
                <option value="BEGINNER">Beginner</option>
                <option value="INTERMEDIATE">Intermediate</option>
                <option value="ADVANCED">Advanced</option>
              </select>
            </label>
            <label>
              <span>Submission Type</span>
              <select value={templateForm.submission_type} onChange={(e) => setTemplateForm((prev) => ({ ...prev, submission_type: e.target.value }))}>
                <option value="CODE">Code</option>
                <option value="DOCUMENT">Document</option>
                <option value="DESIGN">Design</option>
              </select>
            </label>
            <label className="project-form-span-2">
              <span>Short Description</span>
              <input value={templateForm.short_description} onChange={(e) => setTemplateForm((prev) => ({ ...prev, short_description: e.target.value }))} required />
            </label>
            <label className="project-form-span-2">
              <span>Business Problem</span>
              <textarea rows={3} value={templateForm.business_problem} onChange={(e) => setTemplateForm((prev) => ({ ...prev, business_problem: e.target.value }))} />
            </label>
            <label className="project-form-span-2">
              <span>Overview</span>
              <textarea rows={3} value={templateForm.instruction_overview} onChange={(e) => setTemplateForm((prev) => ({ ...prev, instruction_overview: e.target.value }))} />
            </label>
            <label>
              <span>Estimated Hours</span>
              <input type="number" min="1" value={templateForm.estimated_hours} onChange={(e) => setTemplateForm((prev) => ({ ...prev, estimated_hours: e.target.value }))} />
            </label>
            <label>
              <span>Passing Score</span>
              <input type="number" min="0" max="100" value={templateForm.passing_score} onChange={(e) => setTemplateForm((prev) => ({ ...prev, passing_score: e.target.value }))} />
            </label>
            <label className="project-form-span-2">
              <span>Deliverables (one per line)</span>
              <textarea rows={4} value={templateForm.deliverables} onChange={(e) => setTemplateForm((prev) => ({ ...prev, deliverables: e.target.value }))} />
            </label>
            <label className="project-form-span-2">
              <span>Steps (one per line)</span>
              <textarea rows={4} value={templateForm.steps} onChange={(e) => setTemplateForm((prev) => ({ ...prev, steps: e.target.value }))} />
            </label>
            <label className="project-form-span-2">
              <span>Submission Requirements (one per line)</span>
              <textarea rows={3} value={templateForm.submission_requirements} onChange={(e) => setTemplateForm((prev) => ({ ...prev, submission_requirements: e.target.value }))} />
            </label>
            <label>
              <span>Tags (one per line)</span>
              <textarea rows={3} value={templateForm.tags} onChange={(e) => setTemplateForm((prev) => ({ ...prev, tags: e.target.value }))} />
            </label>
            <label>
              <span>Expected Keywords (one per line)</span>
              <textarea rows={3} value={templateForm.expected_keywords} onChange={(e) => setTemplateForm((prev) => ({ ...prev, expected_keywords: e.target.value }))} />
            </label>
            <label>
              <span>Prerequisite Skills (one per line)</span>
              <textarea rows={3} value={templateForm.prerequisite_skills} onChange={(e) => setTemplateForm((prev) => ({ ...prev, prerequisite_skills: e.target.value }))} />
            </label>
            <label>
              <span>Starter Resources (one per line)</span>
              <textarea rows={3} value={templateForm.starter_resources} onChange={(e) => setTemplateForm((prev) => ({ ...prev, starter_resources: e.target.value }))} />
            </label>
            <label className="project-form-span-2">
              <span>Evaluation Notes</span>
              <textarea rows={2} value={templateForm.evaluation_notes} onChange={(e) => setTemplateForm((prev) => ({ ...prev, evaluation_notes: e.target.value }))} />
            </label>
            <label>
              <span>Correctness Weight</span>
              <input type="number" min="0" value={templateForm.correctness_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, correctness_weight: e.target.value }))} />
            </label>
            <label>
              <span>Originality Weight</span>
              <input type="number" min="0" value={templateForm.originality_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, originality_weight: e.target.value }))} />
            </label>
            <label>
              <span>Communication Weight</span>
              <input type="number" min="0" value={templateForm.communication_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, communication_weight: e.target.value }))} />
            </label>
            <label>
              <span>Quality Weight</span>
              <input type="number" min="0" value={templateForm.quality_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, quality_weight: e.target.value }))} />
            </label>
            <label>
              <span>Plagiarism Threshold</span>
              <input type="number" min="0" max="100" value={templateForm.plagiarism_threshold} onChange={(e) => setTemplateForm((prev) => ({ ...prev, plagiarism_threshold: e.target.value }))} />
            </label>
            <label>
              <span>Grammar Weight</span>
              <input type="number" min="0" max="100" value={templateForm.grammar_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, grammar_weight: e.target.value }))} />
            </label>
            <label className="project-checkbox">
              <input type="checkbox" checked={templateForm.allow_auto_accept} onChange={(e) => setTemplateForm((prev) => ({ ...prev, allow_auto_accept: e.target.checked }))} />
              <span>Allow auto-accept</span>
            </label>
            <label className="project-checkbox">
              <input type="checkbox" checked={templateForm.active} onChange={(e) => setTemplateForm((prev) => ({ ...prev, active: e.target.checked }))} />
              <span>Active</span>
            </label>
            <div className="project-form-actions project-form-span-2">
              <button type="submit" className="btn-primary-green" disabled={savingTemplate}>
                {savingTemplate ? 'Saving...' : editingTemplate ? 'Update Template' : 'Create Template'}
              </button>
              {editingTemplate && (
                <button type="button" className="btn-outline-small" onClick={() => { setEditingTemplate(null); setTemplateForm(EMPTY_TEMPLATE_FORM); }}>
                  Cancel Edit
                </button>
              )}
            </div>
          </form>
        </div>

        <div className="project-panel">
          <h2>Manual Assignment</h2>
          <form onSubmit={handleAssign} className="project-form-grid">
            <label>
              <span>Student</span>
              <select value={assignForm.student_id} onChange={(e) => setAssignForm((prev) => ({ ...prev, student_id: e.target.value }))} required>
                <option value="">Select student</option>
                {students.map((student) => (
                  <option key={student.id} value={student.id}>{student.username} ({student.email})</option>
                ))}
              </select>
            </label>
            <label>
              <span>Project</span>
              <select value={assignForm.project_template_id} onChange={(e) => setAssignForm((prev) => ({ ...prev, project_template_id: e.target.value }))} required>
                <option value="">Select template</option>
                {templateOptions.map((template) => (
                  <option key={template.id} value={template.id}>{template.title}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Due Date</span>
              <input type="datetime-local" value={assignForm.due_date} onChange={(e) => setAssignForm((prev) => ({ ...prev, due_date: e.target.value }))} />
            </label>
            <label className="project-form-span-2">
              <span>Assignment Note</span>
              <textarea rows={3} value={assignForm.recommendation_reason} onChange={(e) => setAssignForm((prev) => ({ ...prev, recommendation_reason: e.target.value }))} />
            </label>
            <div className="project-form-actions project-form-span-2">
              <button type="submit" className="btn-primary" disabled={savingAssignment}>
                {savingAssignment ? 'Assigning...' : 'Assign Project'}
              </button>
            </div>
          </form>

          <h2 style={{ marginTop: '1.5rem' }}>Pending Reviews</h2>
          {loading ? (
            <p style={{ color: '#6b7280' }}>Loading...</p>
          ) : pendingSubmissions.length === 0 ? (
            <p style={{ color: '#6b7280' }}>No flagged or pending submissions.</p>
          ) : (
            <div className="pending-submission-list">
              {pendingSubmissions.slice(0, 6).map((submission) => (
                <div key={submission.id} className="pending-submission-item">
                  <strong>{submission.repository_url || submission.artifact_url || `Submission #${submission.id}`}</strong>
                  <span>Status: {submission.status}</span>
                  <span>Feedback: {submission.evaluations?.[0]?.feedback_summary || 'Awaiting review'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="project-panel" style={{ marginTop: '1.5rem' }}>
        <h2>Existing Templates</h2>
        {loading ? (
          <p style={{ color: '#6b7280' }}>Loading templates...</p>
        ) : templates.length === 0 ? (
          <p style={{ color: '#6b7280' }}>No project templates yet.</p>
        ) : (
          <div className="template-list-grid">
            {templates.map((template) => (
              <TemplateListCard
                key={template.id}
                template={template}
                onEdit={(item) => {
                  setEditingTemplate(item);
                  setTemplateForm(mapTemplateToForm(item));
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
