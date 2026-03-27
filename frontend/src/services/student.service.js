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
