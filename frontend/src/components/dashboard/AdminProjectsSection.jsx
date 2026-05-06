import React, { useCallback, useEffect, useState } from 'react';
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

function AdminTemplateExpandedDetails({ template }) {
  const latestCriteria = Array.isArray(template?.rubric?.criteria) ? template.rubric.criteria : [];
  const deliverables = template.instruction?.deliverables || [];
  const submissionReqs = template.instruction?.submission_requirements || [];
  const overview = template.instruction?.overview || '';
  const businessProblem = template.business_problem || '';

  return (
    <div className="admin-template-expand">
      <div className="project-chip-row" style={{ marginBottom: '0.75rem' }}>
        {(template.tags || []).slice(0, 10).map((tag) => <span key={tag} className="project-chip">{tag}</span>)}
      </div>
      <div>
        <div className="admin-template-preview-label">Short description</div>
        {template.short_description ? (
          <p className="admin-template-preview-block">{template.short_description}</p>
        ) : (
          <p className="admin-template-preview-block muted">No short description</p>
        )}
      </div>
      {businessProblem ? (
        <div>
          <div className="admin-template-preview-label">Business problem / scenario</div>
          <p className="admin-template-preview-block">{businessProblem}</p>
        </div>
      ) : null}
      {overview ? (
        <div>
          <div className="admin-template-preview-label">Instruction overview</div>
          <p className="admin-template-preview-block">{overview}</p>
        </div>
      ) : null}
      <div className="template-card-meta-wide">
        <div>
          <div className="admin-template-preview-label">Submission requirements</div>
          {submissionReqs.length > 0 ? (
            <ul className="admin-template-bullet-list">
              {submissionReqs.map((line, idx) => (
                <li key={idx}>{String(line)}</li>
              ))}
            </ul>
          ) : (
            <p className="admin-template-preview-block muted">None listed</p>
          )}
        </div>
        <div>
          <div className="admin-template-preview-label">Deliverables</div>
          {deliverables.length > 0 ? (
            <ul className="admin-template-bullet-list">
              {deliverables.map((line, idx) => (
                <li key={idx}>{String(line)}</li>
              ))}
            </ul>
          ) : (
            <p className="admin-template-preview-block muted">None listed</p>
          )}
        </div>
      </div>
      <div className="project-meta-grid">
        <div>
          <strong>Rubric</strong>
          <div>{latestCriteria.map((item) => `${item.label} ${item.weight}%`).join(' • ') || 'Default rubric'}</div>
        </div>
        <div>
          <strong>Passing / AI</strong>
          <div>
            Pass {template.rubric?.passing_score ?? '—'} • Plagiarism cap {template.rubric?.plagiarism_threshold ?? '—'}%
          </div>
        </div>
      </div>
    </div>
  );
}

function AdminFormSection({ title, hint, children }) {
  return (
    <div className="admin-template-form-section">
      <div className="admin-template-section-head">
        <h3 className="admin-template-section-title">{title}</h3>
        {hint ? <p className="admin-template-section-hint">{hint}</p> : null}
      </div>
      <div className="project-form-grid nested">
        {children}
      </div>
    </div>
  );
}

const DEFAULT_TEMPLATE_PAGE_SIZE = 12;

export default function AdminProjectsSection() {
  const { domains } = useDomains();
  const [templates, setTemplates] = useState([]);
  const [templateCount, setTemplateCount] = useState(0);
  const [templatePage, setTemplatePage] = useState(1);
  const [templatePageSize, setTemplatePageSize] = useState(DEFAULT_TEMPLATE_PAGE_SIZE);
  const [assignTemplateOptions, setAssignTemplateOptions] = useState([]);
  const [expandedTemplateId, setExpandedTemplateId] = useState(null);
  const [students, setStudents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [pendingSubmissions, setPendingSubmissions] = useState([]);
  const [templateForm, setTemplateForm] = useState(EMPTY_TEMPLATE_FORM);
  const [assignForm, setAssignForm] = useState(EMPTY_ASSIGN_FORM);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [savingAssignment, setSavingAssignment] = useState(false);
  const [error, setError] = useState('');

  const loadTemplatesPage = useCallback(async (page, pageSize) => {
    setTemplatesLoading(true);
    try {
      const templateRes = await adminApi.getProjectTemplates({ page, page_size: pageSize });
      const templateData = templateRes?.data;
      if (Array.isArray(templateData)) {
        setTemplates(templateData);
        setTemplateCount(templateData.length);
      } else {
        setTemplates(templateData?.results || []);
        setTemplateCount(typeof templateData?.count === 'number' ? templateData.count : (templateData?.results || []).length);
      }
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load templates.');
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  const loadAssignTemplateChoices = async () => {
    try {
      const res = await adminApi.getProjectTemplates({ page: 1, page_size: 250 });
      const data = res?.data;
      const list = Array.isArray(data) ? data : (data?.results || []);
      setAssignTemplateOptions(list.map((item) => ({ id: item.id, title: item.title })));
    } catch {
      setAssignTemplateOptions([]);
    }
  };

  const loadSupporting = async () => {
    try {
      const [studentRes, summaryRes, pendingRes] = await Promise.all([
        adminApi.getStudents(),
        adminApi.getEvaluationSummary(),
        adminApi.getPendingSubmissions(),
      ]);
      const studentData = studentRes?.data;
      setStudents(Array.isArray(studentData) ? studentData : (studentData?.results || []));
      setSummary(summaryRes?.data || null);
      const pendingData = pendingRes?.data;
      setPendingSubmissions(Array.isArray(pendingData) ? pendingData : (pendingData?.results || []));
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load project data.');
    }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await Promise.all([loadSupporting(), loadAssignTemplateChoices()]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    loadTemplatesPage(templatePage, templatePageSize);
  }, [templatePage, templatePageSize, loadTemplatesPage]);

  const domainOptions = Array.isArray(domains) ? domains : [];
  const templateOptions = assignTemplateOptions;
  const totalTemplatePages = Math.max(1, Math.ceil(Math.max(templateCount, 1) / templatePageSize));

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
      await Promise.all([
        loadSupporting(),
        loadTemplatesPage(templatePage, templatePageSize),
        loadAssignTemplateChoices(),
      ]);
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
      await loadSupporting();
    } catch (err) {
      setError(err.response?.data?.detail || JSON.stringify(err.response?.data || {}) || err.message);
    } finally {
      setSavingAssignment(false);
    }
  };

  const handleDelete = async (template) => {
    if (!window.confirm(`Delete template "${template.title}"?`)) return;
    const wasOnlyOnPage = templates.length === 1;
    try {
      await adminApi.deleteProjectTemplate(template.id);
      if (editingTemplate?.id === template.id) {
        setEditingTemplate(null);
        setTemplateForm(EMPTY_TEMPLATE_FORM);
      }
      if (wasOnlyOnPage && templatePage > 1) {
        setTemplatePage((p) => p - 1);
      } else {
        await loadTemplatesPage(templatePage, templatePageSize);
      }
      await Promise.all([loadSupporting(), loadAssignTemplateChoices()]);
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
        <MetricCard label="Templates" value={summary?.template_count ?? templateCount} />
        <MetricCard label="Assignments" value={summary?.assignment_count ?? 0} />
        <MetricCard label="Flagged" value={summary?.flagged_submissions ?? 0} />
        <MetricCard label="Avg Completed Score" value={summary?.average_completed_score ?? 0} />
      </div>

      <div className="project-two-col">
        <div className="project-panel">
          <h2>{editingTemplate ? 'Edit Template' : 'Create Template'}</h2>
          <form onSubmit={handleTemplateSave} className="project-form-grid">
            <AdminFormSection
              title="Project basics"
              hint="Domain, title, and how this template appears in lists. Short description is the one-line summary students see first."
            >
              <label>
                <span>Domain</span>
                <select value={templateForm.domain_id} onChange={(e) => setTemplateForm((prev) => ({ ...prev, domain_id: e.target.value }))} required>
                  <option value="">Select domain</option>
                  {domainOptions.map((domain) => <option key={domain.id} value={domain.id}>{domain.name}</option>)}
                </select>
              </label>
              <label>
                <span>Title</span>
                <input value={templateForm.title} onChange={(e) => setTemplateForm((prev) => ({ ...prev, title: e.target.value }))} required placeholder="e.g. Build a REST API for tasks" />
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
                <span>Submission type</span>
                <select value={templateForm.submission_type} onChange={(e) => setTemplateForm((prev) => ({ ...prev, submission_type: e.target.value }))}>
                  <option value="CODE">Code (ZIP upload)</option>
                  <option value="DOCUMENT">Document (general written)</option>
                  <option value="DESIGN">Design (visual / UX)</option>
                  <option value="PDF">PDF file</option>
                  <option value="WORD">Word / DOCX</option>
                  <option value="SPREADSHEET">Spreadsheet</option>
                </select>
              </label>
              <label>
                <span>Estimated hours</span>
                <input type="number" min="1" value={templateForm.estimated_hours} onChange={(e) => setTemplateForm((prev) => ({ ...prev, estimated_hours: e.target.value }))} />
              </label>
              <label className="project-checkbox project-form-span-2" style={{ alignSelf: 'end' }}>
                <input type="checkbox" checked={templateForm.active} onChange={(e) => setTemplateForm((prev) => ({ ...prev, active: e.target.checked }))} />
                <span>Active (visible to students &amp; recommenders)</span>
              </label>
              <label className="project-form-span-2">
                <span>Short description (student-facing summary)</span>
                <textarea
                  rows={3}
                  value={templateForm.short_description}
                  onChange={(e) => setTemplateForm((prev) => ({ ...prev, short_description: e.target.value }))}
                  required
                  placeholder="One or two sentences: what the student will build or deliver."
                />
              </label>
            </AdminFormSection>

            <AdminFormSection
              title="Project description &amp; brief"
              hint="Business problem sets the scenario. Instruction overview is the full narrative students read before starting (goals, context, constraints)."
            >
              <label className="project-form-span-2">
                <span>Business problem / scenario</span>
                <textarea
                  rows={4}
                  value={templateForm.business_problem}
                  onChange={(e) => setTemplateForm((prev) => ({ ...prev, business_problem: e.target.value }))}
                  placeholder="Why this project matters; real-world context; what is broken or missing."
                />
              </label>
              <label className="project-form-span-2">
                <span>Instruction overview (full project brief)</span>
                <textarea
                  rows={5}
                  value={templateForm.instruction_overview}
                  onChange={(e) => setTemplateForm((prev) => ({ ...prev, instruction_overview: e.target.value }))}
                  placeholder="Detailed brief: scope, success criteria, what students should learn, links to background reading if any."
                />
              </label>
            </AdminFormSection>

            <AdminFormSection
              title="Steps, deliverables &amp; submission requirements"
              hint="List one item per line. Submission requirements are the rules (file types, repo structure, must-haves) — students and AI grading rely on these."
            >
              <label className="project-form-span-2">
                <span>Steps (one per line)</span>
                <textarea rows={5} value={templateForm.steps} onChange={(e) => setTemplateForm((prev) => ({ ...prev, steps: e.target.value }))} placeholder={'1. …\n2. …'} />
              </label>
              <label className="project-form-span-2">
                <span>Deliverables (one per line)</span>
                <textarea rows={5} value={templateForm.deliverables} onChange={(e) => setTemplateForm((prev) => ({ ...prev, deliverables: e.target.value }))} placeholder="What artifacts they must hand in." />
              </label>
              <label className="project-form-span-2">
                <span>Submission requirements (one per line)</span>
                <textarea
                  rows={6}
                  value={templateForm.submission_requirements}
                  onChange={(e) => setTemplateForm((prev) => ({ ...prev, submission_requirements: e.target.value }))}
                  placeholder="e.g. Upload one ZIP file • Include README with setup steps • Keep file under size limit"
                />
              </label>
            </AdminFormSection>

            <AdminFormSection
              title="Tags, keywords &amp; resources"
              hint="Tags power recommendations. Expected keywords help plagiarism/similarity checks. Starter resources are links or hints (one per line)."
            >
              <label className="project-form-span-2">
                <span>Tags (one per line)</span>
                <textarea rows={3} value={templateForm.tags} onChange={(e) => setTemplateForm((prev) => ({ ...prev, tags: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Expected keywords (one per line)</span>
                <textarea rows={3} value={templateForm.expected_keywords} onChange={(e) => setTemplateForm((prev) => ({ ...prev, expected_keywords: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Prerequisite skills (one per line)</span>
                <textarea rows={3} value={templateForm.prerequisite_skills} onChange={(e) => setTemplateForm((prev) => ({ ...prev, prerequisite_skills: e.target.value }))} />
              </label>
              <label className="project-form-span-2">
                <span>Starter resources (one per line)</span>
                <textarea rows={3} value={templateForm.starter_resources} onChange={(e) => setTemplateForm((prev) => ({ ...prev, starter_resources: e.target.value }))} />
              </label>
            </AdminFormSection>

            <AdminFormSection
              title="AI evaluation &amp; rubric"
              hint="Criterion weights should add up to 100. Evaluation notes guide the AI (and mentors) on what to prioritize when grading."
            >
              <label className="project-form-span-2">
                <span>Evaluation notes (for AI / reviewers)</span>
                <textarea rows={4} value={templateForm.evaluation_notes} onChange={(e) => setTemplateForm((prev) => ({ ...prev, evaluation_notes: e.target.value }))} placeholder="What must be true for a pass; common pitfalls; domain-specific checks." />
              </label>
              <label>
                <span>Passing score (0–100)</span>
                <input type="number" min="0" max="100" value={templateForm.passing_score} onChange={(e) => setTemplateForm((prev) => ({ ...prev, passing_score: e.target.value }))} />
              </label>
              <label>
                <span>Plagiarism similarity threshold (%)</span>
                <input type="number" min="0" max="100" value={templateForm.plagiarism_threshold} onChange={(e) => setTemplateForm((prev) => ({ ...prev, plagiarism_threshold: e.target.value }))} />
              </label>
              <label>
                <span>Correctness weight</span>
                <input type="number" min="0" value={templateForm.correctness_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, correctness_weight: e.target.value }))} />
              </label>
              <label>
                <span>Originality weight</span>
                <input type="number" min="0" value={templateForm.originality_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, originality_weight: e.target.value }))} />
              </label>
              <label>
                <span>Communication weight</span>
                <input type="number" min="0" value={templateForm.communication_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, communication_weight: e.target.value }))} />
              </label>
              <label>
                <span>Quality weight</span>
                <input type="number" min="0" value={templateForm.quality_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, quality_weight: e.target.value }))} />
              </label>
              <label>
                <span>Grammar weight</span>
                <input type="number" min="0" max="100" value={templateForm.grammar_weight} onChange={(e) => setTemplateForm((prev) => ({ ...prev, grammar_weight: e.target.value }))} />
              </label>
              <label className="project-checkbox project-form-span-2">
                <input type="checkbox" checked={templateForm.allow_auto_accept} onChange={(e) => setTemplateForm((prev) => ({ ...prev, allow_auto_accept: e.target.checked }))} />
                <span>Allow auto-accept when score ≥ passing and checks pass</span>
              </label>
            </AdminFormSection>

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
                  <strong>{submission.uploaded_file || `Submission #${submission.id}`}</strong>
                  <span>Status: {submission.status}</span>
                  <span>Feedback: {submission.evaluations?.[0]?.feedback_summary || 'Awaiting review'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="project-panel" style={{ marginTop: '1.5rem' }}>
        <div className="admin-templates-header">
          <h2 style={{ marginBottom: '0.35rem' }}>Existing Templates</h2>
          <p className="section-desc" style={{ margin: 0 }}>Row view with pagination. Click a row to expand the full brief, requirements, and rubric.</p>
        </div>

        <div className="admin-templates-toolbar">
          <label className="admin-templates-page-size">
            <span>Rows per page</span>
            <select
              value={templatePageSize}
              onChange={(e) => {
                setTemplatePageSize(Number(e.target.value));
                setTemplatePage(1);
              }}
            >
              <option value={12}>12</option>
              <option value={24}>24</option>
              <option value={48}>48</option>
            </select>
          </label>
          <div className="admin-templates-pagination">
            <button
              type="button"
              className="btn-outline-small"
              disabled={templatePage <= 1 || templatesLoading}
              onClick={() => setTemplatePage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span className="admin-templates-page-label">
              Page {templatePage} of {totalTemplatePages}
              {' · '}
              {templateCount}
              {' total'}
            </span>
            <button
              type="button"
              className="btn-outline-small"
              disabled={templatePage >= totalTemplatePages || templatesLoading}
              onClick={() => setTemplatePage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>

        {templatesLoading && templates.length === 0 ? (
          <p style={{ color: '#6b7280' }}>Loading templates...</p>
        ) : templateCount === 0 ? (
          <p style={{ color: '#6b7280' }}>No project templates yet.</p>
        ) : (
          <div className={`admin-templates-table-wrap ${templatesLoading ? 'is-loading' : ''}`}>
            <table className="admin-templates-table">
              <thead>
                <tr>
                  <th className="admin-templates-table__chev" aria-hidden="true" />
                  <th>Title</th>
                  <th>Domain</th>
                  <th>Level</th>
                  <th>Active</th>
                  <th className="admin-templates-table__actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => {
                  const expanded = expandedTemplateId === template.id;
                  const titleShort = template.title && template.title.length > 64 ? `${template.title.slice(0, 64)}…` : template.title;
                  return (
                    <React.Fragment key={template.id}>
                      <tr
                        className={`admin-templates-table__row ${expanded ? 'is-expanded' : ''}`}
                        onClick={() => setExpandedTemplateId(expanded ? null : template.id)}
                      >
                        <td className="admin-templates-table__chev" aria-hidden="true">{expanded ? '▼' : '▶'}</td>
                        <td className="admin-templates-table__title" title={template.title}>{titleShort}</td>
                        <td>{template.domain?.name || '—'}</td>
                        <td>{template.complexity}</td>
                        <td>{template.active ? 'Yes' : 'No'}</td>
                        <td className="admin-templates-table__actions" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            className="btn-outline-small"
                            onClick={() => {
                              setEditingTemplate(template);
                              setTemplateForm(mapTemplateToForm(template));
                              setExpandedTemplateId(null);
                              window.scrollTo({ top: 0, behavior: 'smooth' });
                            }}
                          >
                            Edit
                          </button>
                          <button type="button" className="btn-outline-small danger" onClick={() => handleDelete(template)}>Delete</button>
                        </td>
                      </tr>
                      {expanded ? (
                        <tr className="admin-templates-table__detail-row">
                          <td colSpan={6}>
                            <AdminTemplateExpandedDetails template={template} />
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {assignTemplateOptions.length >= 250 && (summary?.template_count ?? templateCount) > 250 ? (
          <p className="admin-templates-assign-hint">Manual assign lists the first 250 templates by id. Use pagination above to find others.</p>
        ) : null}
      </div>
    </div>
  );
}
