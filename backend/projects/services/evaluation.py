import re
from statistics import mean

try:
    from nltk.tokenize import wordpunct_tokenize
except Exception:  # pragma: no cover - fallback when nltk is unavailable locally
    def wordpunct_tokenize(text):
        return re.findall(r'\w+|[^\w\s]', text or '')

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from projects.models import ProjectSubmission, SubmissionEvaluation
from projects.services.recommendation import update_student_progress_snapshot


DEFAULT_METRIC_WEIGHTS = {
    'correctness': 40.0,
    'originality': 25.0,
    'communication': 15.0,
    'quality': 20.0,
}


def _normalize_lines(items):
    return [str(item).strip() for item in (items or []) if str(item).strip()]


def _submission_corpus_text(submission):
    assignment = submission.assignment
    template = assignment.project_template
    instruction = getattr(template, 'instruction', None)
    parts = [
        template.title,
        template.short_description,
        template.business_problem,
        submission.submission_text,
        submission.notes,
        submission.repository_url,
        submission.artifact_url,
        ' '.join(_normalize_lines(submission.submitted_files)),
    ]
    if instruction:
        parts.extend(
            [
                instruction.overview,
                ' '.join(_normalize_lines(instruction.deliverables)),
                ' '.join(_normalize_lines(instruction.steps)),
            ]
        )
    return '\n'.join(part for part in parts if part).strip()


def _split_sentences(text):
    return [s.strip() for s in re.split(r'[.!?]+', text or '') if s.strip()]


def _grammar_score(text, submission_type):
    if not text:
        return 70.0 if submission_type == 'CODE' else 45.0

    tokens = [tok for tok in wordpunct_tokenize(text) if re.search(r'\w', tok)]
    sentences = _split_sentences(text)
    if not tokens:
        return 45.0

    avg_sentence_length = len(tokens) / max(1, len(sentences))
    punctuation_hits = len(re.findall(r'[.,;:!?]', text))
    uppercase_ratio = sum(1 for tok in tokens if tok.isupper() and len(tok) > 1) / max(1, len(tokens))
    long_token_ratio = sum(1 for tok in tokens if len(tok) > 16) / max(1, len(tokens))

    score = 78.0
    if avg_sentence_length > 35:
        score -= 10
    elif avg_sentence_length < 4:
        score -= 12
    if punctuation_hits < max(1, len(sentences) - 1):
        score -= 8
    if uppercase_ratio > 0.15:
        score -= 10
    if long_token_ratio > 0.2:
        score -= 6
    if len(tokens) > 120:
        score += 8
    return max(0.0, min(100.0, round(score, 2)))


def _correctness_score(submission):
    assignment = submission.assignment
    template = assignment.project_template
    instruction = getattr(template, 'instruction', None)

    keywords = set(_normalize_lines(template.expected_keywords))
    deliverables = set(_normalize_lines(getattr(instruction, 'deliverables', [])))
    submission_text = _submission_corpus_text(submission).lower()

    coverage_hits = 0
    coverage_total = len(keywords | deliverables)
    for token in keywords | deliverables:
        normalized = token.lower()
        if normalized and normalized in submission_text:
            coverage_hits += 1

    coverage_score = (coverage_hits / coverage_total * 100) if coverage_total else 70.0
    completeness_bonus = 0.0
    if submission.repository_url:
        completeness_bonus += 10.0
    if submission.artifact_url:
        completeness_bonus += 8.0
    if submission.submission_text and len(submission.submission_text.strip()) >= 120:
        completeness_bonus += 12.0
    if submission.notes:
        completeness_bonus += 5.0

    return max(0.0, min(100.0, round(coverage_score * 0.7 + completeness_bonus, 2)))


def _quality_score(submission):
    text = submission.submission_text or ''
    notes = submission.notes or ''
    body = f'{text}\n{notes}'.strip()
    if not body:
        return 55.0

    paragraph_count = len([p for p in body.split('\n') if p.strip()])
    checklist_markers = len(re.findall(r'(^|\n)([-*]|\d+\.)\s+', body))
    link_count = len(re.findall(r'https?://', body))

    score = 62.0
    if paragraph_count >= 3:
        score += 12
    if checklist_markers >= 2:
        score += 10
    if link_count >= 1:
        score += 6
    if len(body) >= 400:
        score += 10
    return max(0.0, min(100.0, round(score, 2)))


def _originality_score(submission):
    current_text = _submission_corpus_text(submission)
    if not current_text:
        return 50.0, 50.0

    historical_texts = list(
        ProjectSubmission.objects.exclude(id=submission.id)
        .filter(assignment__project_template=submission.assignment.project_template)
        .values_list('submission_text', flat=True)
    )
    corpus = [current_text] + [text for text in historical_texts if text]
    if len(corpus) < 2:
        return 100.0, 0.0

    vectorizer = TfidfVectorizer(stop_words='english')
    matrix = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    max_similarity = float(similarities.max()) if similarities.size else 0.0
    originality_score = max(0.0, round(100.0 - (max_similarity * 100.0), 2))
    return originality_score, round(max_similarity * 100.0, 2)


def _design_quality_score(submission):
    assignment = submission.assignment
    template = assignment.project_template
    score = 60.0
    if submission.artifact_url:
        score += 20
    if submission.repository_url and template.submission_type == 'CODE':
        score += 10
    if submission.notes and len(submission.notes.strip()) >= 80:
        score += 10
    if submission.submission_text and len(submission.submission_text.strip()) >= 180:
        score += 8
    return max(0.0, min(100.0, round(score, 2)))


def _rubric_scores(rubric, metrics):
    criteria = rubric.criteria or []
    if not criteria:
        criteria = [
            {'key': key, 'label': key.title(), 'weight': weight}
            for key, weight in DEFAULT_METRIC_WEIGHTS.items()
        ]
    normalized = {}
    total_weight = 0.0
    weighted_total = 0.0
    for criterion in criteria:
        key = criterion.get('key', 'quality')
        label = criterion.get('label', key.title())
        weight = float(criterion.get('weight', 0))
        total_weight += weight
        if key == 'correctness':
            score = metrics['correctness_score']
        elif key in ('originality', 'plagiarism'):
            score = metrics['originality_score']
        elif key in ('communication', 'grammar'):
            score = metrics['grammar_score']
        elif key in ('quality', 'design'):
            score = mean([
                metrics['design_quality_score'],
                metrics['correctness_score'],
                metrics['quality_score'],
            ])
        else:
            score = mean(list(metrics.values()))
        weighted_total += score * weight
        normalized[key] = {
            'label': label,
            'weight': weight,
            'score': round(score, 2),
            'description': criterion.get('description', ''),
        }
    overall = weighted_total / total_weight if total_weight else mean(list(metrics.values()))
    return normalized, round(overall, 2)


def _build_feedback(submission, metrics, similarity_pct, overall_score, decision):
    strengths = []
    improvements = []
    flags = []

    if metrics['correctness_score'] >= 75:
        strengths.append('Your submission covers most of the expected requirements.')
    else:
        improvements.append('Add more evidence that each project requirement has been completed.')

    if metrics['grammar_score'] >= 75:
        strengths.append('Your explanation is clear and easy to follow.')
    else:
        improvements.append('Improve clarity, grammar, and structure in your explanation or notes.')

    if similarity_pct >= 75:
        flags.append('High similarity detected. Manual review recommended.')
    elif similarity_pct >= 45:
        flags.append('Moderate similarity detected. Review originality before resubmitting.')
    else:
        strengths.append('Originality check did not detect major overlap with prior submissions.')

    if metrics['design_quality_score'] < 65:
        improvements.append('Include clearer deliverables, links, or supporting artifacts to strengthen quality.')

    if decision == 'ACCEPTED':
        summary = (
            f'Accepted with an overall score of {overall_score:.1f}. '
            'The submission is complete enough to move the student forward.'
        )
    elif decision == 'NEEDS_MENTOR_REVIEW':
        summary = (
            f'Flagged for mentor review with an overall score of {overall_score:.1f}. '
            'Potential originality or confidence issues need manual verification.'
        )
    else:
        summary = (
            f'Revision required with an overall score of {overall_score:.1f}. '
            'The student should improve the highlighted areas and submit again.'
        )

    return strengths, improvements, flags, summary


def evaluate_submission(submission):
    assignment = submission.assignment
    template = assignment.project_template
    rubric = template.rubric

    correctness_score = _correctness_score(submission)
    originality_score, similarity_pct = _originality_score(submission)
    grammar_score = _grammar_score(
        submission.submission_text or submission.notes,
        template.submission_type,
    )
    design_quality_score = _design_quality_score(submission)
    quality_score = _quality_score(submission)

    metrics = {
        'correctness_score': correctness_score,
        'originality_score': originality_score,
        'grammar_score': grammar_score,
        'design_quality_score': design_quality_score,
        'quality_score': quality_score,
    }
    rubric_scores, overall_score = _rubric_scores(rubric, metrics)

    if similarity_pct >= rubric.plagiarism_threshold:
        decision = 'NEEDS_MENTOR_REVIEW'
    elif overall_score >= rubric.passing_score and rubric.allow_auto_accept:
        decision = 'ACCEPTED'
    else:
        decision = 'REVISE_AND_RESUBMIT'

    strengths, improvements, flags, summary = _build_feedback(
        submission,
        metrics,
        similarity_pct,
        overall_score,
        decision,
    )

    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        overall_score=overall_score,
        correctness_score=correctness_score,
        originality_score=originality_score,
        grammar_score=grammar_score,
        design_quality_score=design_quality_score,
        rubric_scores=rubric_scores,
        strengths=strengths,
        improvements=improvements,
        flags=flags,
        decision=decision,
        feedback_summary=summary,
        evaluation_payload={
            'similarity_percentage': similarity_pct,
            'metrics': metrics,
        },
    )

    submission.status = 'FLAGGED' if decision == 'NEEDS_MENTOR_REVIEW' else 'EVALUATED'
    submission.metadata = {
        **(submission.metadata or {}),
        'similarity_percentage': similarity_pct,
        'evaluated_with': evaluation.model_name,
    }
    submission.save(update_fields=['status', 'metadata'])

    assignment.latest_evaluation_score = overall_score
    assignment.latest_feedback_summary = summary
    if decision == 'ACCEPTED':
        assignment.status = 'COMPLETED'
        assignment.completed_at = submission.submitted_at
    elif decision == 'NEEDS_MENTOR_REVIEW':
        assignment.status = 'SUBMITTED'
    else:
        assignment.status = 'NEEDS_REVISION'
    assignment.save(
        update_fields=[
            'latest_evaluation_score',
            'latest_feedback_summary',
            'status',
            'completed_at',
        ]
    )

    update_student_progress_snapshot(assignment.student)
    return evaluation
