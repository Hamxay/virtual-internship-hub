"""
Pre-AI checks before calling Gemini (FR4): Python syntax (CODE) and TF-IDF similarity.
"""
from __future__ import annotations

import ast
import logging
import re
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from projects.models import ProjectSubmission

from .extractor import SubmissionExtractResult, combined_extract_text

logger = logging.getLogger(__name__)

# Strictly greater than 75% per spec ("similarity > 75%").
PLAGIARISM_STOP_THRESHOLD_PERCENT = 75.0
PLAGIARISM_RECENT_SUBMISSIONS = 100


def _looks_like_python_source(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return False
    return bool(re.search(r'^\s*(def |class |import |from \w+ import )', text, re.MULTILINE))


def _should_run_python_syntax_check(submission, extract_body: str) -> bool:
    if submission.assignment.project_template.submission_type != 'CODE':
        return False
    url = (submission.repository_url or '').lower()
    if '.py' in url and 'github.com' in url:
        return True
    if _looks_like_python_source(extract_body):
        return True
    st = (submission.submission_text or '').strip()
    if st and _looks_like_python_source(st):
        return True
    return False


def syntax_gatekeeper_result(submission, extract: SubmissionExtractResult) -> Optional[str]:
    """
    If Python syntax check applies and ``ast.parse`` fails, return error message.
    Otherwise return None (pass or skip).
    """
    body = combined_extract_text(extract)
    # Multi-file repository bundles are not valid single-module Python; skip ``ast``.
    if '===== FILE:' in body:
        return None
    if not _should_run_python_syntax_check(submission, body):
        return None
    if not body.strip():
        return None
    try:
        ast.parse(body, filename='<submission>', mode='exec')
    except SyntaxError as exc:
        return exc.msg or 'invalid syntax'
    except (MemoryError, UnicodeDecodeError) as exc:
        return str(exc)
    return None


def pre_ai_plagiarism_max_similarity_percent(submission, extract: SubmissionExtractResult) -> float:
    """
    TF-IDF cosine vs recent submissions on the same template (excluding self).
    Returns max similarity in [0, 100] scale; 0 when comparison is skipped.
    """
    from projects.services.evaluation import _submission_corpus_text

    current = combined_extract_text(extract).strip() or _submission_corpus_text(submission).strip()
    if not current:
        return 0.0

    qs = (
        ProjectSubmission.objects.exclude(pk=submission.pk)
        .filter(assignment__project_template_id=submission.assignment.project_template_id)
        .order_by('-submitted_at')[:PLAGIARISM_RECENT_SUBMISSIONS]
    )
    historical_texts = []
    for other in qs:
        t = _submission_corpus_text(other).strip()
        if t:
            historical_texts.append(t)

    if not historical_texts:
        return 0.0

    corpus = [current] + historical_texts
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        matrix = vectorizer.fit_transform(corpus)
        similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
        max_similarity = float(similarities.max()) if similarities.size else 0.0
    except Exception as exc:
        logger.warning('Pre-AI plagiarism vectorizer failed: %s', exc)
        return 0.0

    return round(max_similarity * 100.0, 2)


def plagiarism_gatekeeper_triggers(similarity_percent: float) -> bool:
    return similarity_percent > PLAGIARISM_STOP_THRESHOLD_PERCENT
