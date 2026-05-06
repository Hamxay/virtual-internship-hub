import json
import logging
import re
from statistics import mean

import requests
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
    empty_content_gatekeeper,
    plagiarism_gatekeeper_triggers,
    pre_ai_plagiarism_max_similarity_percent,
    syntax_gatekeeper_result,
)
from projects.services.extractor import SubmissionExtractResult
from projects.services.recommendation import (
    apply_fr4_recommended_difficulty_if_higher,
    update_student_progress_snapshot,
)
from projects.utils.code_flattener import UniversalRepositoryFlattener
from projects.utils.document_extractor import UniversalDocumentExtractor
from projects.utils.prompt_builder import build_evaluation_prompt

logger = logging.getLogger(__name__)


def _project_eval_model_id() -> str:
    name = (getattr(settings, 'OPENROUTER_PROJECT_EVAL_MODEL', None) or '').strip()
    if name:
        return name
    chat_default = (getattr(settings, 'OPENROUTER_CHAT_MODEL', None) or '').strip()
    return chat_default or 'meta-llama/llama-3.3-70b-instruct:free'


def _strip_json_fences(raw_text: str) -> str:
    text = (raw_text or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE).strip()
        if text.endswith('```'):
            text = text[: text.rfind('```')].strip()
    return text


def _parse_model_json(raw_text: str) -> dict:
    cleaned = _strip_json_fences(raw_text)
    return json.loads(cleaned)


def _validate_fr4_payload(data: dict) -> dict:
    """
    Strict FR4 schema validation for model output.

    Required keys:
    - overall_score: integer 0..100
    - improvements: non-empty string
    - extracted_tags: list[str]

    Optional keys:
    - correctness_score, originality_score, grammar_score, design_quality_score: 0..100
    - recommended_next_difficulty / difficulty_recommendation: BEGINNER|INTERMEDIATE|ADVANCED
    """
    if not isinstance(data, dict):
        raise ValueError('Model response must be a JSON object.')

    allowed_keys = {
        'overall_score',
        'improvements',
        'extracted_tags',
        'correctness_score',
        'originality_score',
        'grammar_score',
        'design_quality_score',
        'recommended_next_difficulty',
        'difficulty_recommendation',
    }
    unknown = sorted(set(data.keys()) - allowed_keys)
    if unknown:
        raise ValueError(f'Model response contains unsupported keys: {", ".join(unknown)}')

    required_keys = {'overall_score', 'improvements', 'extracted_tags'}
    missing = sorted(required_keys - set(data.keys()))
    if missing:
        raise ValueError(f'Model response missing required keys: {", ".join(missing)}')

    try:
        overall_score = int(data['overall_score'])
    except (TypeError, ValueError):
        raise ValueError('overall_score must be an integer.') from None
    if overall_score < 0 or overall_score > 100:
        raise ValueError('overall_score must be between 0 and 100.')

    improvements = data['improvements']
    if not isinstance(improvements, str) or not improvements.strip():
        raise ValueError('improvements must be a non-empty string.')

    extracted_tags = data['extracted_tags']
    if not isinstance(extracted_tags, list):
        raise ValueError('extracted_tags must be an array of strings.')
    normalized_tags = []
    for tag in extracted_tags:
        if not isinstance(tag, str):
            raise ValueError('extracted_tags must contain only strings.')
        cleaned = tag.strip()
        if cleaned:
            normalized_tags.append(cleaned[:80])

    normalized = {
        **data,
        'overall_score': overall_score,
        'improvements': improvements.strip(),
        'extracted_tags': normalized_tags[:25],
    }

    score_keys = (
        'correctness_score',
        'originality_score',
        'grammar_score',
        'design_quality_score',
    )
    for key in score_keys:
        if key not in normalized:
            continue
        value = normalized[key]
        if value is None and key == 'design_quality_score':
            # Keep null semantics for non-applicable design dimension.
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            raise ValueError(f'{key} must be numeric in range 0..100.') from None
        if score < 0 or score > 100:
            raise ValueError(f'{key} must be in range 0..100.')
        normalized[key] = score

    difficulty_keys = ('recommended_next_difficulty', 'difficulty_recommendation')
    for key in difficulty_keys:
        if key not in normalized:
            continue
        raw = normalized[key]
        if raw is None:
            continue
        label = str(raw).upper().strip()
        if label not in {'BEGINNER', 'INTERMEDIATE', 'ADVANCED'}:
            raise ValueError(f'{key} must be BEGINNER, INTERMEDIATE, or ADVANCED.')
        normalized[key] = label

    return normalized


def _build_fr4_student_bundle(submission: ProjectSubmission) -> tuple[str, SubmissionExtractResult]:
    """
    Build student bundle from notes/text and uploaded file path.
    Returns ``(student_text_for_prompt, gatekeeper_extract)``.
    """
    sections: list[str] = []

    notes = (submission.notes or '').strip()
    stext = (submission.submission_text or '').strip()
    if notes:
        sections.append(f'## Student notes\n{notes}')
    if stext:
        sections.append(f'## Student submission text\n{stext}')

    try:
        uploaded = submission.uploaded_file
        if uploaded and getattr(uploaded, 'name', None):
            try:
                abs_path = uploaded.path
            except Exception:
                abs_path = None
            if abs_path:
                if str(uploaded.name).lower().endswith('.zip'):
                    flattened = UniversalRepositoryFlattener().flatten_local_zip(abs_path)
                    if flattened:
                        sections.append(f'## Uploaded code archive\n{flattened}')
                else:
                    outcome = UniversalDocumentExtractor.process(abs_path)
                    if outcome.text_markdown:
                        sections.append(outcome.text_markdown)
    except Exception as exc:
        logger.exception('Document extraction failed: %s', exc)
        sections.append(f'## Uploaded document\n(Document processing failed: {exc})')

    rendered = '\n\n'.join(s for s in sections if s).strip() or '(No extractable student content.)'

    gate = SubmissionExtractResult()
    gate.text_parts = [rendered] if rendered else []
    return rendered, gate


def _run_openrouter_evaluation(submission: ProjectSubmission, student_text: str) -> dict:
    api_key = (getattr(settings, 'OPENROUTER_API_KEY', '') or '').strip()
    if not str(api_key).strip():
        raise RuntimeError('OPENROUTER_API_KEY is not configured.')

    base = (getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1') or '').rstrip('/')
    if not base:
        raise RuntimeError('OPENROUTER_BASE_URL is not configured.')
    model_id = _project_eval_model_id()
    template = submission.assignment.project_template
    system_instruction, user_prompt = build_evaluation_prompt(template, student_text)
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    referer = (getattr(settings, 'OPENROUTER_HTTP_REFERER', '') or '').strip()
    if referer:
        headers['HTTP-Referer'] = referer
    title = (getattr(settings, 'OPENROUTER_APP_TITLE', '') or '').strip()
    if title:
        headers['X-Title'] = title
        headers['X-OpenRouter-Title'] = title
    payload = {
        'model': model_id,
        'temperature': 0.1,
        'messages': [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    try:
        response = requests.post(f'{base}/chat/completions', headers=headers, json=payload, timeout=(20, 180))
    except requests.RequestException as exc:
        raise RuntimeError(f'OpenRouter network failure: {exc}') from exc
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(f'OpenRouter returned non-JSON response (status {response.status_code}).') from None
    if response.status_code >= 400:
        err = data.get('error') if isinstance(data, dict) else None
        msg = err.get('message') if isinstance(err, dict) else str(data)
        raise RuntimeError(f'OpenRouter error ({response.status_code}): {msg}')
    choices = data.get('choices') if isinstance(data, dict) else None
    if not choices:
        raise RuntimeError('OpenRouter returned no choices.')
    message = choices[0].get('message') if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise RuntimeError('OpenRouter returned invalid choice payload.')
    content = message.get('content')
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                parts.append(item['text'])
            elif isinstance(item, str):
                parts.append(item)
        raw_text = ''.join(parts).strip()
    else:
        raw_text = str(content or '').strip()
    if not raw_text:
        raise RuntimeError('OpenRouter returned empty response content.')
    parsed = _parse_model_json(raw_text)
    return _validate_fr4_payload(parsed)


def _coerce_fr4_int_score(value, default=0) -> int:
    try:
        if value is None:
            return default
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _persist_syntax_gate_failure(submission, error_msg: str) -> SubmissionEvaluation:
    """Python ``ast`` gatekeeper failed — correctness 0, pipeline stops before LLM evaluation."""
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


def _persist_empty_content_gate_failure(submission) -> SubmissionEvaluation:
    """No extractable content — stops pipeline without LLM call."""
    assignment = submission.assignment
    improvements_msg = (
        'Your submission did not contain any readable content and could not be evaluated. '
        'If you submitted a GitHub repository URL, make sure the repository is public and the URL is correct. '
        'Please re-upload using a supported file type and make sure the ZIP/file is not empty.'
    )
    summary = 'Submission returned no readable content and could not be evaluated.'
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='fr4_empty_content_gatekeeper',
        overall_score=0.0,
        correctness_score=0.0,
        originality_score=0.0,
        grammar_score=0.0,
        design_quality_score=0.0,
        rubric_scores={'gatekeeper': 'empty_content'},
        strengths=[],
        improvements=[improvements_msg],
        flags=['EMPTY_SUBMISSION'],
        decision='REVISE_AND_RESUBMIT',
        feedback_summary=summary,
        evaluation_payload={'gatekeeper': 'empty_content'},
    )
    submission.status = 'EVALUATED'
    submission.metadata = {
        **(submission.metadata or {}),
        'empty_content_gate_failed': True,
        'evaluated_with': 'fr4_empty_content_gatekeeper',
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
    """TF-IDF similarity > 75% vs recent same-template submissions — FLAGGED, no LLM call."""
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
    """Persist OpenRouter JSON (FR4 schema) to SubmissionEvaluation, assignment, and snapshot."""
    assignment = submission.assignment

    overall_score = float(_coerce_fr4_int_score(data.get('overall_score'), 0))
    o_int = int(overall_score)
    if 'correctness_score' in data:
        correctness_score = float(_coerce_fr4_int_score(data.get('correctness_score'), o_int))
    else:
        correctness_score = float(o_int)
    if 'originality_score' in data:
        originality_score = float(_coerce_fr4_int_score(data.get('originality_score'), o_int))
    else:
        originality_score = float(o_int)
    if 'grammar_score' in data:
        grammar_score = float(_coerce_fr4_int_score(data.get('grammar_score'), o_int))
    else:
        grammar_score = float(o_int)

    design_raw = data.get('design_quality_score', None) if 'design_quality_score' in data else None
    design_null = design_raw is None
    if design_null:
        design_quality_score = 0.0
    else:
        design_quality_score = float(_coerce_fr4_int_score(design_raw, o_int))

    raw_improvements = data.get('improvements')
    if isinstance(raw_improvements, str):
        improvements = [raw_improvements.strip()] if raw_improvements.strip() else []
    elif isinstance(raw_improvements, list):
        improvements = [str(s).strip() for s in raw_improvements if str(s).strip()]
    else:
        improvements = []

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

    rubric = getattr(submission.assignment.project_template, 'rubric', None)
    passing_threshold = float(rubric.passing_score) if rubric else 75.0
    passed_fr4 = overall_score >= passing_threshold
    # FR5: strong AI scores go to mentor; do not auto-complete the assignment.
    decision = 'NEEDS_MENTOR_REVIEW' if passed_fr4 else 'REVISE_AND_RESUBMIT'

    rubric_payload = {
        'fr4_json': data,
        'extracted_tags': extracted_tags,
        'design_quality_score_applicable': not design_null,
    }

    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name=_project_eval_model_id(),
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
            'source': 'openrouter_fr4',
            'design_quality_score_null': design_null,
        },
    )

    submission.status = 'EVALUATED'
    submission.metadata = {
        **(submission.metadata or {}),
        'evaluated_with': _project_eval_model_id(),
        'fr4_recommended_next_difficulty': difficulty_raw,
        'fr4_extracted_tags': extracted_tags,
    }
    submission.save(update_fields=['status', 'metadata'])

    assignment.latest_evaluation_score = overall_score
    assignment.latest_feedback_summary = feedback_summary
    if passed_fr4:
        assignment.status = 'PENDING_MENTOR_REVIEW'
        assignment.completed_at = None
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
    if submission.uploaded_file:
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
    score = 60.0
    if submission.uploaded_file:
        score += 20
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
        rubric = getattr(submission.assignment.project_template, 'rubric', None)
        plagiarism_thr = float(rubric.plagiarism_threshold) if rubric else 75.0
        if similarity_pct >= plagiarism_thr:
            summary = (
                f'Flagged for mentor review with an overall score of {overall_score:.1f}. '
                'Potential originality or confidence issues need manual verification.'
            )
        else:
            summary = (
                f'Overall score {overall_score:.1f} meets the passing bar; '
                'a mentor must confirm before this assignment is marked complete.'
            )
    else:
        summary = (
            f'Revision required with an overall score of {overall_score:.1f}. '
            'The student should improve the highlighted areas and submit again.'
        )

    return strengths, improvements, flags, summary


def evaluate_submission_heuristic(submission):
    """
    Legacy local evaluator (TF-IDF / rubric heuristics). Used when OpenRouter is unavailable.
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
        # FR5: same as model path — mentor confirms before completion (no auto ACCEPTED).
        decision = 'NEEDS_MENTOR_REVIEW'
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
    if decision == 'NEEDS_MENTOR_REVIEW':
        if similarity_pct >= rubric.plagiarism_threshold:
            assignment.status = 'SUBMITTED'
        else:
            assignment.status = 'PENDING_MENTOR_REVIEW'
        assignment.completed_at = None
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
    return evaluation


def evaluate_submission_logic(submission_id: int) -> SubmissionEvaluation:
    """
    FR4: pre-AI gatekeepers, OpenRouter JSON evaluation, or heuristic fallback.

    Syntax / plagiarism checks run before OpenRouter (and before heuristic fallback) to save tokens
    and enforce policy. Persistence is wrapped in ``transaction.atomic`` per path.
    """
    submission = ProjectSubmission.objects.select_related(
        'assignment__student',
        'assignment__project_template__instruction',
        'assignment__project_template__rubric',
    ).get(pk=submission_id)
    if submission.evaluations.exists():
        return submission.evaluations.order_by('-reviewed_at', '-id').first()

    try:
        student_text, extract = _build_fr4_student_bundle(submission)
    except Exception as exc:
        logger.exception('FR4 student bundle failed for submission %s: %s', submission_id, exc)
        student_text = (
            (submission.submission_text or '').strip()
            or (submission.notes or '').strip()
            or '(No extractable student content.)'
        )
        extract = SubmissionExtractResult()
        extract.text_parts = [student_text]

    if empty_content_gatekeeper(student_text):
        with transaction.atomic():
            return _persist_empty_content_gate_failure(submission)

    syntax_msg = syntax_gatekeeper_result(submission, extract)
    if syntax_msg:
        with transaction.atomic():
            return _persist_syntax_gate_failure(submission, syntax_msg)

    similarity_pct = pre_ai_plagiarism_max_similarity_percent(submission, extract)
    if plagiarism_gatekeeper_triggers(similarity_pct):
        with transaction.atomic():
            return _persist_plagiarism_gate_failure(submission, similarity_pct)

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '') or ''

    if not str(api_key).strip():
        logger.warning('OPENROUTER_API_KEY missing; using heuristic evaluator for submission %s', submission_id)
        with transaction.atomic():
            return evaluate_submission_heuristic(submission)

    try:
        parsed = _run_openrouter_evaluation(submission, student_text)
    except Exception as exc:
        logger.exception('OpenRouter evaluation failed for submission %s: %s', submission_id, exc)
        with transaction.atomic():
            return evaluate_submission_heuristic(submission)

    with transaction.atomic():
        return _apply_parsed_evaluation(submission, parsed)
