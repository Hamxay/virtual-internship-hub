/**
 * Student-facing copy for tasks / projects.
 * API still uses enums and snake_case; UI maps them here.
 */

const SUBMISSION_TYPE_LABELS = {
  CODE: 'GitHub code',
  DOCUMENT: 'Written document',
  DESIGN: 'Design file',
  PDF: 'PDF',
  WORD: 'Word document',
  SPREADSHEET: 'Spreadsheet',
};

const COMPLEXITY_LABELS = {
  BEGINNER: 'Beginner',
  INTERMEDIATE: 'Intermediate',
  ADVANCED: 'Advanced',
};

const ASSIGNMENT_STATUS_LABELS = {
  RECOMMENDED: 'Suggested',
  IN_PROGRESS: 'In progress',
  SUBMITTED: 'Waiting for review',
  PENDING_MENTOR_REVIEW: 'Awaiting mentor',
  NEEDS_REVISION: 'Try again',
  COMPLETED: 'Completed',
};

/** How students hand work in (shown under project title). */
export function handInTypeLabel(submissionType) {
  if (!submissionType) return '';
  return SUBMISSION_TYPE_LABELS[submissionType] || submissionType;
}

/** Difficulty band from template. */
export function levelLabel(complexity) {
  if (!complexity) return '';
  return COMPLEXITY_LABELS[complexity] || String(complexity).replace(/_/g, ' ');
}

/** Assignment lifecycle (row badge). */
export function taskStatusLabel(status) {
  if (!status) return '';
  return ASSIGNMENT_STATUS_LABELS[status] || String(status).replace(/_/g, ' ');
}

/** One-line summary: Domain · level · format · hours */
export function projectSummaryLine(template) {
  const t = template || {};
  const parts = [
    t.domain?.name,
    levelLabel(t.complexity),
    handInTypeLabel(t.submission_type),
    t.estimated_hours != null ? `~${t.estimated_hours} h` : '',
  ].filter(Boolean);
  return parts.join(' · ') || '—';
}

/** Map API validation keys to form labels (errors only). */
const API_FIELD_LABELS = {
  repository_url: 'GitHub link',
  uploaded_file: 'Your file',
  artifact_url: 'Demo link',
  submission_text: 'Summary',
  notes: 'Notes',
  submitted_files: 'Key files list',
  non_field_errors: 'Form',
};

export function friendlyApiFieldName(key) {
  return API_FIELD_LABELS[key] || key.replace(/_/g, ' ');
}

/**
 * Softer wording when showing template "submission requirements" (still the same meaning).
 */
export function friendlyRequirementLine(text) {
  let s = String(text || '');
  const pairs = [
    [/Artifact URL/gi, 'File or share link'],
    [/Repository URL/gi, 'GitHub or code link'],
    [/Submission text/gi, 'Written answer in the form'],
    [/Virtual Internship Hub submission form/gi, 'The hand-in form'],
    [/submission form/gi, 'hand-in form'],
  ];
  pairs.forEach(([re, to]) => {
    s = s.replace(re, to);
  });
  return s;
}
