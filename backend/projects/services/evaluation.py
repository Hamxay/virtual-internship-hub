import json
import logging
import re
from statistics import mean

from django.conf import settings
from django.db import transaction
from django.utils import timezone

try:
    from nltk.tokenize import wordpunct_tokenize
except Exception:  # pragma: no cover - fallback when nltk is unavailable locally
    def wordpunct_tokenize(text):
        return re.findall(r'\w+|[^\w\s]', text or '')

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from projects.models import ProjectSubmission, SubmissionEvaluation
from projects.services.evaluation_gatekeepers import (
    PLAGIARISM_STOP_THRESHOLD_PERCENT,
    plagiarism_gatekeeper_triggers,
    pre_ai_plagiarism_max_similarity_percent,
    syntax_gatekeeper_result,
)
from projects.services.extractor import extract_submission_for_evaluation
from projects.services.recommendation import (
    apply_fr4_recommended_difficulty_if_higher,
    update_student_progress_snapshot,
)

logger = logging.getLogger(__name__)

GEMINI_MODEL_NAME = 'gemini-1.5-flash'

FR4_SYSTEM_PROMPT = """You are a Senior Technical Mentor evaluating a student project submission.
Return ONLY valid JSON (no markdown fences). Be fair, specific, and constructive.
All score fields MUST be integers from 0 to 100 inclusive unless design_quality_score is null.
Use null for design_quality_score only when there is no meaningful design aspect to assess.
"""


def _strip_json_fences(raw_text: str) -> str:
    text = (raw_text or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE).strip()
        if text.endswith('```'):
            text = text[: text.rfind('```')].strip()
    return text


def _parse_gemini_json(raw_text: str) -> dict:
    cleaned = _strip_json_fences(raw_text)
    return json.loads(cleaned)


def _build_fr4_user_prompt(submission, extract_text_body: str) -> str:
    assignment = submission.assignment
    template = assignment.project_template
    instruction = getattr(template, 'instruction', None)
    rubric = getattr(template, 'rubric', None)

    lines = [
        f'## Project title\n{template.title}',
        f'## Short description\n{template.short_description or ""}',
        f'## Business problem\n{template.business_problem or ""}',
        f'## Template complexity\n{template.complexity}',
        f'## Submission type\n{template.submission_type}',
    ]
    if instruction:
        lines.extend(
            [
                f'## Instruction overview\n{instruction.overview or ""}',
                f'## Steps\n{json.dumps(instruction.steps or [], indent=2)}',
                f'## Deliverables\n{json.dumps(instruction.deliverables or [], indent=2)}',
                f'## Submission requirements\n{json.dumps(instruction.submission_requirements or [], indent=2)}',
                f'## Evaluation notes (for graders)\n{instruction.evaluation_notes or ""}',
            ]
        )
    if rubric:
        lines.extend(
            [
                f'## Rubric passing score\n{rubric.passing_score}',
                f'## Rubric criteria\n{json.dumps(rubric.criteria or [], indent=2)}',
            ]
        )
    lines.append('## Extracted student content (text and described artifacts)\n' + (extract_text_body or '(no text extracted)'))
    lines.append(
        '\n## Required JSON shape (exact keys; application/json)\n'
        '{\n'
        '  "overall_score": <int 0-100>,\n'
        '  "correctness_score": <int 0-100>,\n'
        '  "originality_score": <int 0-100>,\n'
        '  "grammar_score": <int 0-100>,\n'
        '  "design_quality_score": <int 0-100> | null,\n'
        '  "improvements": ["..."],\n'
        '  "extracted_tags": ["short topic or skill tags"],\n'
        '  "recommended_next_difficulty": "BEGINNER" | "INTERMEDIATE" | "ADVANCED"\n'
        '}\n'
        'Omit no keys except use null only for design_quality_score when not applicable.'
    )
    return '\n'.join(lines)


def _run_gemini_evaluation(submission, extract) -> dict:
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not str(api_key).strip():
        raise RuntimeError('GEMINI_API_KEY is not configured.')

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError('google-generativeai is not installed.') from exc

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        GEMINI_MODEL_NAME,
        system_instruction=FR4_SYSTEM_PROMPT,
        generation_config={'response_mime_type': 'application/json'},
    )

    combined_text = '\n\n'.join(extract.text_parts)
    user_prompt = _build_fr4_user_prompt(submission, combined_text)

    uploaded_handles = []
    try:
        for local_path in extract.gemini_local_paths:
            uploaded_handles.append(genai.upload_file(local_path))

        content_parts = uploaded_handles + [user_prompt]
        response = model.generate_content(content_parts)
        try:
            raw_text = response.text
        except ValueError as exc:
            raise RuntimeError('Gemini returned no text (blocked or empty response).') from exc
        if not raw_text:
            raise RuntimeError('Empty response from Gemini.')
        return _parse_gemini_json(raw_text)
    finally:
        for handle in uploaded_handles:
            try:
                genai.delete_file(handle.name)
            except Exception as cleanup_error:
                logger.warning('Could not delete uploaded Gemini file %s: %s', handle.name, cleanup_error)


def _coerce_fr4_int_score(value, default=0) -> int:
    try:
        if value is None:
            return default
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _persist_syntax_gate_failure(submission, error_msg: str) -> SubmissionEvaluation:
    """Python ``ast`` gatekeeper failed — correctness 0, pipeline stops before Gemini."""
    assignment = submission.assignment
    summary = 'Submission failed automatic Python syntax validation.'
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='fr4_syntax_gatekeeper',
        overall_score=0.0,
        correctness_score=0.0,
        originality_score=0.0,
        grammar_score=0.0,
        design_quality_score=0.0,
        rubric_scores={'gatekeeper': 'syntax', 'syntax_error': error_msg},
        strengths=[],
        improvements=[f'Python syntax error: {error_msg}'],
        flags=['SYNTAX_ERROR'],
        decision='REVISE_AND_RESUBMIT',
        feedback_summary=summary,
        evaluation_payload={'gatekeeper': 'syntax', 'syntax_error': error_msg},
    )
    submission.status = 'EVALUATED'
    submission.metadata = {
        **(submission.metadata or {}),
        'syntax_gate_failed': True,
        'evaluated_with': 'fr4_syntax_gatekeeper',
    }
    submission.save(update_fields=['status', 'metadata'])
    assignment.latest_evaluation_score = 0.0
    assignment.latest_feedback_summary = summary
    assignment.status = 'NEEDS_REVISION'
    assignment.completed_at = None
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


def _persist_plagiarism_gate_failure(submission, similarity_pct: float) -> SubmissionEvaluation:
    """TF-IDF similarity > 75% vs recent same-template submissions — FLAGGED, no Gemini."""
    assignment = submission.assignment
    summary = (
        f'Submission flagged: content similarity {similarity_pct:.1f}% exceeds the '
        f'{PLAGIARISM_STOP_THRESHOLD_PERCENT}% threshold.'
    )
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='fr4_plagiarism_gatekeeper',
        overall_score=0.0,
        correctness_score=0.0,
        originality_score=0.0,
        grammar_score=0.0,
        design_quality_score=0.0,
        rubric_scores={
            'gatekeeper': 'plagiarism',
            'similarity_percent': similarity_pct,
        },
        strengths=[],
        improvements=[
            'Automated review detected very high similarity to prior submissions on this project. '
            'A mentor will review.'
        ],
        flags=['PLAGIARISM_SUSPECT', f'similarity_{similarity_pct:.1f}_percent'],
        decision='NEEDS_MENTOR_REVIEW',
        feedback_summary=summary,
        evaluation_payload={
            'gatekeeper': 'plagiarism',
            'similarity_percent': similarity_pct,
        },
    )
    submission.status = 'FLAGGED'
    submission.metadata = {
        **(submission.metadata or {}),
        'plagiarism_similarity_percent': similarity_pct,
        'evaluated_with': 'fr4_plagiarism_gatekeeper',
    }
    submission.save(update_fields=['status', 'metadata'])
    assignment.latest_evaluation_score = 0.0
    assignment.latest_feedback_summary = summary
    assignment.status = 'SUBMITTED'
    assignment.completed_at = None
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


def _apply_parsed_evaluation(submission, data: dict) -> SubmissionEvaluation:
    """Persist Gemini JSON (FR4 schema) to SubmissionEvaluation, assignment, and snapshot."""
    assignment = submission.assignment

    overall_score = float(_coerce_fr4_int_score(data.get('overall_score'), 0))
    correctness_score = float(_coerce_fr4_int_score(data.get('correctness_score'), int(overall_score)))
    originality_score = float(_coerce_fr4_int_score(data.get('originality_score'), int(overall_score)))
    grammar_score = float(_coerce_fr4_int_score(data.get('grammar_score'), int(overall_score)))

    design_raw = data.get('design_quality_score')
    design_null = design_raw is None
    if design_null:
        design_quality_score = 0.0
    else:
        design_quality_score = float(_coerce_fr4_int_score(design_raw, int(overall_score)))

    improvements = data.get('improvements') or []
    if not isinstance(improvements, list):
        improvements = [str(improvements)]
    improvements = [str(s).strip() for s in improvements if str(s).strip()]

    extracted_tags = data.get('extracted_tags') or []
    if not isinstance(extracted_tags, list):
        extracted_tags = [str(extracted_tags)]
    extracted_tags = [str(t).strip() for t in extracted_tags if str(t).strip()]

    difficulty_raw = str(
        data.get('recommended_next_difficulty') or data.get('difficulty_recommendation') or 'BEGINNER'
    ).upper().strip()
    if difficulty_raw not in {'BEGINNER', 'INTERMEDIATE', 'ADVANCED'}:
        difficulty_raw = 'BEGINNER'

    if improvements:
        feedback_summary = ' '.join(improvements[:4])
        if len(feedback_summary) > 2000:
            feedback_summary = feedback_summary[:1997] + '...'
    else:
        feedback_summary = f'Overall score {overall_score:.0f}/100. Review feedback and resubmit if needed.'

    strengths = []

    passed_fr4 = overall_score >= 75.0
    decision = 'ACCEPTED' if passed_fr4 else 'REVISE_AND_RESUBMIT'

    rubric_payload = {
        'fr4_json': data,
        'extracted_tags': extracted_tags,
        'design_quality_score_applicable': not design_null,
    }

    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name=GEMINI_MODEL_NAME,
        overall_score=overall_score,
        correctness_score=correctness_score,
        originality_score=originality_score,
        grammar_score=grammar_score,
        design_quality_score=design_quality_score,
        rubric_scores=rubric_payload,
        strengths=strengths,
        improvements=improvements,
        flags=[],
        decision=decision,
        feedback_summary=feedback_summary,
        evaluation_payload={
            'recommended_next_difficulty': difficulty_raw,
            'source': 'gemini_fr4',
            'design_quality_score_null': design_null,
        },
    )

    submission.status = 'EVALUATED'
    submission.metadata = {
        **(submission.metadata or {}),
        'evaluated_with': GEMINI_MODEL_NAME,
        'fr4_recommended_next_difficulty': difficulty_raw,
        'fr4_extracted_tags': extracted_tags,
    }
    submission.save(update_fields=['status', 'metadata'])

    assignment.latest_evaluation_score = overall_score
    assignment.latest_feedback_summary = feedback_summary
    if passed_fr4:
        assignment.status = 'COMPLETED'
        assignment.completed_at = timezone.now()
    else:
        assignment.status = 'NEEDS_REVISION'
        assignment.completed_at = None
    assignment.save(
        update_fields=[
            'latest_evaluation_score',
            'latest_feedback_summary',
            'status',
            'completed_at',
        ]
    )

    update_student_progress_snapshot(assignment.student)
    apply_fr4_recommended_difficulty_if_higher(assignment.student, difficulty_raw)
    return evaluation


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


def evaluate_submission_heuristic(submission):
    """
    Legacy local evaluator (TF-IDF / rubric heuristics). Used when Gemini is unavailable.
    All ORM writes run inside ``transaction.atomic`` via ``evaluate_submission_logic``.
    """
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
        model_name='local_hybrid_v1',
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


def evaluate_submission_logic(submission_id: int) -> SubmissionEvaluation:
    """
    FR4: pre-AI gatekeepers, Gemini 1.5 Flash JSON evaluation, or heuristic fallback.

    Syntax / plagiarism checks run before Gemini (and before heuristic fallback) to save tokens
    and enforce policy. Persistence is wrapped in ``transaction.atomic`` per path.
    """
    submission = ProjectSubmission.objects.select_related(
        'assignment__student',
        'assignment__project_template__instruction',
        'assignment__project_template__rubric',
    ).get(pk=submission_id)

    extract = extract_submission_for_evaluation(submission)

    syntax_msg = syntax_gatekeeper_result(submission, extract)
    if syntax_msg:
        with transaction.atomic():
            return _persist_syntax_gate_failure(submission, syntax_msg)

    similarity_pct = pre_ai_plagiarism_max_similarity_percent(submission, extract)
    if plagiarism_gatekeeper_triggers(similarity_pct):
        with transaction.atomic():
            return _persist_plagiarism_gate_failure(submission, similarity_pct)

    api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''

    if not str(api_key).strip():
        logger.warning('GEMINI_API_KEY missing; using heuristic evaluator for submission %s', submission_id)
        with transaction.atomic():
            return evaluate_submission_heuristic(submission)

    try:
        parsed = _run_gemini_evaluation(submission, extract)
    except Exception as exc:
        logger.exception('Gemini evaluation failed for submission %s: %s', submission_id, exc)
        with transaction.atomic():
            return evaluate_submission_heuristic(submission)

    with transaction.atomic():
        return _apply_parsed_evaluation(submission, parsed)
