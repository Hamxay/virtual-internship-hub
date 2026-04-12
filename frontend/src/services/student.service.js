/**
 * Student payload builders — profile, assessment, project submissions.
 */

import { friendlyApiFieldName } from './studentTasksLabels';

const FILE_SUBMISSION_TYPES = new Set(['DOCUMENT', 'DESIGN', 'PDF', 'WORD', 'SPREADSHEET']);
const MAX_FILE_MB = 15;

export function isFileSubmissionType(submissionType) {
  return submissionType && FILE_SUBMISSION_TYPES.has(submissionType);
}

export function formatSubmissionError(err) {
  const data = err?.response?.data;
  if (!data) return err?.message || 'Request failed.';
  if (typeof data === 'string') return data;
  if (data.detail) return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
  return Object.entries(data)
    .map(([k, v]) => {
      const label = friendlyApiFieldName(k);
      const msg = Array.isArray(v) ? v.join(' ') : String(v);
      return `${label}: ${msg}`;
    })
    .join(' ') || JSON.stringify(data);
}

function submittedFilesLines(form) {
  return String(form.submitted_files || '')
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * JSON body for CODE / legacy, or FormData for file-based project types.
 */
export function buildProjectSubmissionPayload(form, template) {
  const type = template?.submission_type;
  const notes = String(form.notes || '').trim();
  const submission_text = String(form.submission_text || '').trim();
  const artifact_url = String(form.artifact_url || '').trim();
  const lines = submittedFilesLines(form);

  if (type === 'CODE') {
    return {
      repository_url: String(form.repository_url || '').trim(),
      artifact_url,
      submission_text,
      notes,
      submitted_files: lines,
    };
  }

  if (isFileSubmissionType(type)) {
    const file = form.uploaded_file;
    if (!file || !(file instanceof File)) {
      throw new Error('Please choose a file to upload.');
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      throw new Error(`File must be under ${MAX_FILE_MB} MB.`);
    }
    const fd = new FormData();
    fd.append('uploaded_file', file);
    if (notes) fd.append('notes', notes);
    if (submission_text) fd.append('submission_text', submission_text);
    if (artifact_url) fd.append('artifact_url', artifact_url);
    if (lines.length) fd.append('submitted_files', JSON.stringify(lines));
    return fd;
  }

  return {
    repository_url: String(form.repository_url || '').trim(),
    artifact_url,
    submission_text,
    notes,
    submitted_files: lines,
  };
}

export function buildProfileUpdatePayload(targetDomainIds) {
  return { target_domain_ids: targetDomainIds };
}

export function buildAssessmentSubmitPayload(questions, selectedAnswers, submissionToken) {
  const answers = (questions || []).map((q, i) => ({
    question_id: q.id,
    selected_option: selectedAnswers[i] || 'A',
  }));
  return {
    submission_token: submissionToken,
    answers,
  };
}
