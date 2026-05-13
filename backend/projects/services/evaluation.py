import json
import logging
import re
from pathlib import Path

import requests
from django.conf import settings
from django.db import transaction

from projects.models import ProjectSubmission, SubmissionEvaluation
from projects.services.evaluation_gatekeepers import (
    EMPTY_SUBMISSION_PLACEHOLDER,
    get_python_syntax_rejection_message_or_none,
    is_submission_text_bundle_empty,
)
from projects.services.copyleaks import is_copyleaks_enabled, submit_text_scan
from projects.services.local_plagiarism import compute_local_similarity_percent
from projects.services.extractor import SubmissionExtractResult
from projects.services.recommendation import (
    apply_recommended_difficulty_if_higher,
    update_student_progress_snapshot,
)
from projects.services import design_vision
from projects.utils.code_flattener import UniversalRepositoryFlattener
from projects.utils.document_extractor import UniversalDocumentExtractor
from projects.utils.prompt_builder import build_evaluation_prompt

logger = logging.getLogger(__name__)
PROJECT_PASSING_SCORE = 70.0


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


def _validate_model_payload(model_payload: dict) -> dict:
    """Enforce the JSON shape returned by the grading model before we persist it."""
    if not isinstance(model_payload, dict):
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
    unknown = sorted(set(model_payload.keys()) - allowed_keys)
    if unknown:
        raise ValueError(f'Model response contains unsupported keys: {", ".join(unknown)}')

    required_keys = {'overall_score', 'improvements', 'extracted_tags'}
    missing = sorted(required_keys - set(model_payload.keys()))
    if missing:
        raise ValueError(f'Model response missing required keys: {", ".join(missing)}')

    try:
        overall_score = int(model_payload['overall_score'])
    except (TypeError, ValueError):
        raise ValueError('overall_score must be an integer.') from None
    if overall_score < 0 or overall_score > 100:
        raise ValueError('overall_score must be between 0 and 100.')

    improvements = model_payload['improvements']
    if not isinstance(improvements, str) or not improvements.strip():
        raise ValueError('improvements must be a non-empty string.')

    extracted_tags = model_payload['extracted_tags']
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
        **model_payload,
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


def build_submission_bundle_for_evaluation(submission: ProjectSubmission) -> tuple[str, SubmissionExtractResult]:
    """Merge notes, text field, and extracted upload into one string for scoring."""
    sections: list[str] = []
    template = submission.assignment.project_template

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
                    suffix = Path(uploaded.name).suffix.lower()
                    vision_md = None
                    if template.submission_type == 'DESIGN' and suffix in design_vision.DESIGN_IMAGE_SUFFIXES:
                        vision_md = design_vision.build_design_submission_vision_markdown(abs_path, template)
                    if vision_md:
                        sections.append(vision_md)
                    else:
                        outcome = UniversalDocumentExtractor.process(abs_path)
                        if outcome.text_markdown:
                            sections.append(outcome.text_markdown)
    except Exception as exc:
        logger.exception('Document extraction failed: %s', exc)
        sections.append(f'## Uploaded document\n(Document processing failed: {exc})')

    rendered = '\n\n'.join(s for s in sections if s).strip() or EMPTY_SUBMISSION_PLACEHOLDER

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
        response_json = response.json()
    except ValueError:
        raise RuntimeError(f'OpenRouter returned non-JSON response (status {response.status_code}).') from None
    if response.status_code >= 400:
        err = response_json.get('error') if isinstance(response_json, dict) else None
        msg = err.get('message') if isinstance(err, dict) else str(response_json)
        raise RuntimeError(f'OpenRouter error ({response.status_code}): {msg}')
    choices = response_json.get('choices') if isinstance(response_json, dict) else None
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
    return _validate_model_payload(parsed)


def _coerce_int_score(value, default=0) -> int:
    try:
        if value is None:
            return default
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _persist_syntax_gate_failure(submission, error_msg: str) -> SubmissionEvaluation:
    """Syntax gate failed: record a zero score and stop before OpenRouter."""
    assignment = submission.assignment
    summary = 'Submission failed automatic Python syntax validation.'
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='syntax_gatekeeper',
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
        'evaluated_with': 'syntax_gatekeeper',
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
    """No readable student content after extraction."""
    assignment = submission.assignment
    improvements_msg = (
        'Your submission did not contain any readable content and could not be evaluated. '
        'Please re-upload using a supported file type and make sure the ZIP/file is not empty.'
    )
    summary = 'Submission returned no readable content and could not be evaluated.'
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='empty_content_gatekeeper',
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
        'evaluated_with': 'empty_content_gatekeeper',
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


def _persist_local_plagiarism_gate_failure(
    submission: ProjectSubmission, *, similarity_percent: float, threshold: float
) -> SubmissionEvaluation:
    assignment = submission.assignment
    summary = (
        f'Local plagiarism scan flagged this submission: '
        f'{similarity_percent:.1f}% similarity exceeds {threshold:.0f}% threshold.'
    )
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='local_plagiarism_gatekeeper',
        overall_score=0.0,
        correctness_score=0.0,
        originality_score=0.0,
        grammar_score=0.0,
        design_quality_score=0.0,
        rubric_scores={
            'gatekeeper': 'local_plagiarism',
            'similarity_percent': similarity_percent,
            'threshold': threshold,
            'method': 'tfidf_cosine_similarity',
        },
        strengths=[],
        improvements=[
            (
                'High similarity detected by local TF-IDF plagiarism scan. '
                'Please revise and add more original content before resubmitting.'
            )
        ],
        flags=['PLAGIARISM_SUSPECT', f'local_similarity_{similarity_percent:.1f}_percent'],
        decision='NEEDS_MENTOR_REVIEW',
        feedback_summary=summary,
        evaluation_payload={'source': 'local_tfidf', 'similarity_percent': similarity_percent},
    )

    submission.status = 'FLAGGED'
    submission.metadata = {
        **(submission.metadata or {}),
        'plagiarism_similarity_percent': similarity_percent,
        'plagiarism_source': 'local_tfidf',
    }
    submission.save(update_fields=['status', 'metadata'])

    assignment.status = 'SUBMITTED'
    assignment.latest_evaluation_score = 0.0
    assignment.latest_feedback_summary = summary
    assignment.completed_at = None
    assignment.save(
        update_fields=[
            'status',
            'latest_evaluation_score',
            'latest_feedback_summary',
            'completed_at',
        ]
    )
    update_student_progress_snapshot(assignment.student)
    return evaluation


def _persist_copyleaks_gate_failure(
    submission: ProjectSubmission, *, similarity_percent: float, threshold: float
) -> SubmissionEvaluation:
    assignment = submission.assignment
    summary = (
        f'Copyleaks scan flagged this submission: '
        f'{similarity_percent:.1f}% similarity exceeds {threshold:.0f}% threshold.'
    )
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='copyleaks_plagiarism_gatekeeper',
        overall_score=0.0,
        correctness_score=0.0,
        originality_score=0.0,
        grammar_score=0.0,
        design_quality_score=0.0,
        rubric_scores={
            'gatekeeper': 'copyleaks_plagiarism',
            'similarity_percent': similarity_percent,
            'threshold': threshold,
            'provider': 'copyleaks',
        },
        strengths=[],
        improvements=['High similarity detected by Copyleaks; mentor review required.'],
        flags=['PLAGIARISM_SUSPECT', f'copyleaks_similarity_{similarity_percent:.1f}_percent'],
        decision='NEEDS_MENTOR_REVIEW',
        feedback_summary=summary,
        evaluation_payload={'source': 'copyleaks', 'similarity_percent': similarity_percent},
    )

    submission.status = 'FLAGGED'
    submission.metadata = {
        **(submission.metadata or {}),
        'plagiarism_similarity_percent': similarity_percent,
        'plagiarism_source': 'copyleaks',
        'plagiarism_status': 'completed',
        'copyleaks_similarity_percent': similarity_percent,
        'copyleaks_scan_status': 'completed',
    }
    submission.save(update_fields=['status', 'metadata'])

    assignment.status = 'SUBMITTED'
    assignment.latest_evaluation_score = 0.0
    assignment.latest_feedback_summary = summary
    assignment.completed_at = None
    assignment.save(
        update_fields=[
            'status',
            'latest_evaluation_score',
            'latest_feedback_summary',
            'completed_at',
        ]
    )
    update_student_progress_snapshot(assignment.student)
    return evaluation


def _persist_openrouter_evaluation_unavailable(
    submission: ProjectSubmission, *, reason: str, detail: str = ''
) -> SubmissionEvaluation:
    """OpenRouter missing or failed; persist an explicit failure row for the student."""
    assignment = submission.assignment
    detail_bit = f' ({detail})' if detail else ''
    improvements_msg = (
        f'Automated evaluation could not run: {reason}{detail_bit}. '
        'Please try again later or contact support if this persists.'
    )
    summary = 'AI evaluation service unavailable; no score was produced.'
    evaluation = SubmissionEvaluation.objects.create(
        submission=submission,
        model_name='openrouter_unavailable',
        overall_score=0.0,
        correctness_score=0.0,
        originality_score=0.0,
        grammar_score=0.0,
        design_quality_score=0.0,
        rubric_scores={'gatekeeper': 'openrouter_unavailable', 'reason': reason},
        strengths=[],
        improvements=[improvements_msg],
        flags=['OPENROUTER_UNAVAILABLE'],
        decision='REVISE_AND_RESUBMIT',
        feedback_summary=summary,
        evaluation_payload={'reason': reason, 'detail': (detail or '')[:500]},
    )
    submission.status = 'EVALUATED'
    submission.metadata = {
        **(submission.metadata or {}),
        'evaluated_with': 'openrouter_unavailable',
        'openrouter_failure_reason': reason[:200],
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


def _apply_parsed_evaluation(
    submission,
    eval_payload: dict,
    *,
    plagiarism_similarity_percent: float | None,
    plagiarism_source: str,
) -> SubmissionEvaluation:
    """Write validated model JSON to ``SubmissionEvaluation`` and bump assignment state."""
    assignment = submission.assignment

    overall_score = float(_coerce_int_score(eval_payload.get('overall_score'), 0))
    o_int = int(overall_score)
    if 'correctness_score' in eval_payload:
        correctness_score = float(_coerce_int_score(eval_payload.get('correctness_score'), o_int))
    else:
        correctness_score = float(o_int)
    if 'originality_score' in eval_payload:
        originality_score = float(_coerce_int_score(eval_payload.get('originality_score'), o_int))
    else:
        originality_score = float(o_int)
    if 'grammar_score' in eval_payload:
        grammar_score = float(_coerce_int_score(eval_payload.get('grammar_score'), o_int))
    else:
        grammar_score = float(o_int)

    design_raw = (
        eval_payload.get('design_quality_score', None) if 'design_quality_score' in eval_payload else None
    )
    design_null = design_raw is None
    if design_null:
        design_quality_score = 0.0
    else:
        design_quality_score = float(_coerce_int_score(design_raw, o_int))

    raw_improvements = eval_payload.get('improvements')
    if isinstance(raw_improvements, str):
        improvements = [raw_improvements.strip()] if raw_improvements.strip() else []
    elif isinstance(raw_improvements, list):
        improvements = [str(s).strip() for s in raw_improvements if str(s).strip()]
    else:
        improvements = []

    extracted_tags = eval_payload.get('extracted_tags') or []
    if not isinstance(extracted_tags, list):
        extracted_tags = [str(extracted_tags)]
    extracted_tags = [str(t).strip() for t in extracted_tags if str(t).strip()]

    difficulty_raw = str(
        eval_payload.get('recommended_next_difficulty')
        or eval_payload.get('difficulty_recommendation')
        or 'BEGINNER'
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

    # Product rule: all projects use a fixed pass threshold of 70.
    passing_threshold = PROJECT_PASSING_SCORE
    passed_threshold = overall_score >= passing_threshold
    decision = 'NEEDS_MENTOR_REVIEW' if passed_threshold else 'REVISE_AND_RESUBMIT'

    rubric_payload = {
        'model_json': eval_payload,
        'extracted_tags': extracted_tags,
        'design_quality_score_applicable': not design_null,
        'plagiarism_similarity_percent': plagiarism_similarity_percent,
        'plagiarism_source': plagiarism_source,
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
            'source': 'openrouter',
            'design_quality_score_null': design_null,
            'plagiarism_similarity_percent': plagiarism_similarity_percent,
            'plagiarism_source': plagiarism_source,
        },
    )

    submission.status = 'EVALUATED'
    submission.metadata = {
        **(submission.metadata or {}),
        'evaluated_with': _project_eval_model_id(),
        'recommended_next_difficulty': difficulty_raw,
        'extracted_tags': extracted_tags,
        'plagiarism_similarity_percent': plagiarism_similarity_percent,
        'plagiarism_source': plagiarism_source,
    }
    submission.save(update_fields=['status', 'metadata'])

    assignment.latest_evaluation_score = overall_score
    assignment.latest_feedback_summary = feedback_summary
    if passed_threshold:
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
    apply_recommended_difficulty_if_higher(assignment.student, difficulty_raw)
    return evaluation


def evaluate_submission_logic(submission_id: int) -> SubmissionEvaluation:
    """Bundle text → plagiarism gate (Copyleaks/local) → OpenRouter JSON → persist evaluation."""
    submission = ProjectSubmission.objects.select_related(
        'assignment__student',
        'assignment__project_template__instruction',
        'assignment__project_template__rubric',
    ).get(pk=submission_id)
    if submission.evaluations.exists():
        return submission.evaluations.order_by('-reviewed_at', '-id').first()

    try:
        student_text, extract = build_submission_bundle_for_evaluation(submission)
    except Exception as exc:
        logger.exception('Student bundle build failed for submission %s: %s', submission_id, exc)
        student_text = (
            (submission.submission_text or '').strip()
            or (submission.notes or '').strip()
            or EMPTY_SUBMISSION_PLACEHOLDER
        )
        extract = SubmissionExtractResult()
        extract.text_parts = [student_text]

    if is_submission_text_bundle_empty(student_text):
        with transaction.atomic():
            return _persist_empty_content_gate_failure(submission)

    syntax_rejection = get_python_syntax_rejection_message_or_none(submission, extract)
    if syntax_rejection:
        with transaction.atomic():
            return _persist_syntax_gate_failure(submission, syntax_rejection)

    rubric = getattr(submission.assignment.project_template, 'rubric', None)
    plagiarism_threshold = float(rubric.plagiarism_threshold) if rubric else 75.0

    meta = submission.metadata if isinstance(submission.metadata, dict) else {}
    plagiarism_source = str(meta.get('plagiarism_source') or '').strip().lower()
    use_copyleaks = is_copyleaks_enabled()
    if use_copyleaks:
        existing_scan_id = (
            meta.get('plagiarism_scan_id')
            or meta.get('copyleaks_scan_id')
        )
        existing_scan_status = str(
            meta.get('plagiarism_status')
            or meta.get('copyleaks_scan_status')
            or ''
        ).lower()
        already_submitted = bool(
            existing_scan_id and existing_scan_status in {'submitted', 'completed'}
        )
        if not already_submitted:
            scan_result = submit_text_scan(submission_id=submission.pk, text=student_text)
            if scan_result.submitted and scan_result.scan_id:
                meta = {
                    **meta,
                    'plagiarism_provider': 'copyleaks',
                    'plagiarism_source': 'copyleaks',
                    'plagiarism_scan_id': scan_result.scan_id,
                    'plagiarism_status': 'submitted',
                    'copyleaks_scan_id': scan_result.scan_id,
                    'copyleaks_scan_status': 'submitted',
                }
                submission.metadata = meta
                submission.save(update_fields=['metadata'])
                logger.info(
                    'Submitted Copyleaks scan submission=%s scan_id=%s',
                    submission.pk,
                    scan_result.scan_id,
                )
            else:
                meta = {
                    **meta,
                    'plagiarism_provider': 'copyleaks',
                    'plagiarism_source': 'copyleaks',
                    'plagiarism_status': 'not_submitted',
                    'copyleaks_scan_status': 'not_submitted',
                    'copyleaks_error': (scan_result.error or 'Unknown Copyleaks error')[:300],
                }
                submission.metadata = meta
                submission.save(update_fields=['metadata'])
                logger.warning(
                    'Copyleaks submit failed submission=%s error=%s',
                    submission.pk,
                    scan_result.error or 'unknown',
                )

        current_meta = submission.metadata if isinstance(submission.metadata, dict) else {}
        current_scan_id = current_meta.get('plagiarism_scan_id') or current_meta.get('copyleaks_scan_id')
        current_status = str(
            current_meta.get('plagiarism_status')
            or current_meta.get('copyleaks_scan_status')
            or ''
        ).lower()
        if current_scan_id and current_status != 'completed':
            logger.info(
                'Waiting for Copyleaks webhook completion submission=%s scan_id=%s status=%s',
                submission.pk,
                current_scan_id,
                current_status or 'unknown',
            )
            return submission.evaluations.order_by('-reviewed_at', '-id').first()

        plagiarism_similarity_percent = current_meta.get('plagiarism_similarity_percent')
        if plagiarism_similarity_percent in ('', None):
            plagiarism_similarity_percent = current_meta.get('copyleaks_similarity_percent')
        try:
            plagiarism_similarity_percent = (
                round(float(plagiarism_similarity_percent), 2)
                if plagiarism_similarity_percent not in (None, '')
                else None
            )
        except (TypeError, ValueError):
            plagiarism_similarity_percent = None
        plagiarism_source = 'copyleaks'
    else:
        plagiarism_similarity_percent = compute_local_similarity_percent(submission, student_text)
        plagiarism_source = 'local_tfidf'

        if (
            plagiarism_similarity_percent is not None
            and plagiarism_similarity_percent > plagiarism_threshold
        ):
            with transaction.atomic():
                return _persist_local_plagiarism_gate_failure(
                    submission,
                    similarity_percent=plagiarism_similarity_percent,
                    threshold=plagiarism_threshold,
                )

    if (
        plagiarism_source == 'copyleaks'
        and plagiarism_similarity_percent is not None
        and plagiarism_similarity_percent > plagiarism_threshold
    ):
        with transaction.atomic():
            return _persist_copyleaks_gate_failure(
                submission,
                similarity_percent=plagiarism_similarity_percent,
                threshold=plagiarism_threshold,
            )

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '') or ''

    if not str(api_key).strip():
        logger.warning('OPENROUTER_API_KEY missing for submission %s', submission_id)
        with transaction.atomic():
            return _persist_openrouter_evaluation_unavailable(
                submission, reason='OPENROUTER_API_KEY is not configured', detail=''
            )

    try:
        parsed = _run_openrouter_evaluation(submission, student_text)
    except Exception as exc:
        logger.exception('OpenRouter evaluation failed for submission %s: %s', submission_id, exc)
        with transaction.atomic():
            return _persist_openrouter_evaluation_unavailable(
                submission, reason='OpenRouter request or JSON validation failed', detail=str(exc)[:400]
            )

    with transaction.atomic():
        return _apply_parsed_evaluation(
            submission,
            parsed,
            plagiarism_similarity_percent=plagiarism_similarity_percent,
            plagiarism_source=plagiarism_source,
        )
