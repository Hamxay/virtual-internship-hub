/**
 * Admin payload builders: domain create/update, question create/update.
 * Used by AdminDashboard; no API calls here.
 */

export function buildDomainPayload(form) {
  return {
    name: (form.name || '').trim(),
    code: (form.code || '').trim(),
    description: (form.description || '').trim() || '',
  };
}

export function buildQuestionPayload(questionForm, editingQuestion, questionsTotalCount) {
  return {
    text: questionForm.text,
    option_a: questionForm.option_a,
    option_b: questionForm.option_b,
    option_c: questionForm.option_c,
    option_d: questionForm.option_d,
    correct_option: questionForm.correct_option,
    complexity: questionForm.complexity || 'MEDIUM',
    order: editingQuestion ? Number(questionForm.order) : questionsTotalCount,
    points: Number(questionForm.points) || 1,
  };
}

function splitLines(value) {
  return String(value || '')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function buildProjectTemplatePayload(form) {
  return {
    domain_id: Number(form.domain_id),
    title: String(form.title || '').trim(),
    short_description: String(form.short_description || '').trim(),
    business_problem: String(form.business_problem || '').trim(),
    complexity: form.complexity || 'BEGINNER',
    submission_type: form.submission_type || 'CODE',
    estimated_hours: Number(form.estimated_hours) || 8,
    tags: splitLines(form.tags),
    prerequisite_skills: splitLines(form.prerequisite_skills),
    expected_keywords: splitLines(form.expected_keywords),
    active: Boolean(form.active),
    instruction: {
      overview: String(form.instruction_overview || '').trim(),
      steps: splitLines(form.steps),
      deliverables: splitLines(form.deliverables),
      submission_requirements: splitLines(form.submission_requirements),
      starter_resources: splitLines(form.starter_resources),
      evaluation_notes: String(form.evaluation_notes || '').trim(),
    },
    rubric: {
      passing_score: Number(form.passing_score) || 70,
      allow_auto_accept: Boolean(form.allow_auto_accept),
      plagiarism_threshold: Number(form.plagiarism_threshold) || 75,
      grammar_weight: Number(form.grammar_weight) || 15,
      criteria: [
        {
          key: 'correctness',
          label: 'Correctness',
          description: 'Meets the project requirements.',
          weight: Number(form.correctness_weight) || 40,
        },
        {
          key: 'originality',
          label: 'Originality',
          description: 'Shows original work with low similarity.',
          weight: Number(form.originality_weight) || 25,
        },
        {
          key: 'communication',
          label: 'Communication',
          description: 'Clear explanation and documentation.',
          weight: Number(form.communication_weight) || 15,
        },
        {
          key: 'quality',
          label: 'Quality',
          description: 'Overall completeness and presentation quality.',
          weight: Number(form.quality_weight) || 20,
        },
      ],
    },
  };
}

export function buildProjectAssignPayload(form) {
  return {
    student_id: Number(form.student_id),
    project_template_id: Number(form.project_template_id),
    due_date: form.due_date || null,
    recommendation_reason: String(form.recommendation_reason || '').trim(),
  };
}
