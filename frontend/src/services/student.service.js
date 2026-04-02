/**
 * Student payload builders: profile update, assessment submit.
 * Used by StudentDashboard; no API calls here.
 */

export function buildProfileUpdatePayload(targetDomainIds) {
  return { target_domain_ids: targetDomainIds };
}

/**
 * @param {Array} questions - From GET composed (same order as selectedAnswers)
 * @param {Array} selectedAnswers - 'A'|'B'|'C'|'D' per question
 * @param {string} submissionToken - UUID from GET composed (submission_token)
 */
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

export function buildProjectSubmissionPayload(form) {
  const splitFiles = String(form.submitted_files || '')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
  return {
    repository_url: String(form.repository_url || '').trim(),
    artifact_url: String(form.artifact_url || '').trim(),
    submission_text: String(form.submission_text || '').trim(),
    notes: String(form.notes || '').trim(),
    submitted_files: splitFiles,
  };
}
