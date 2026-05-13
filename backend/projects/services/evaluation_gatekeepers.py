"""Pre-LLM gates: empty bundle and optional ``ast.parse`` for single-file Python CODE uploads."""
from __future__ import annotations

import ast
import logging
import re
from typing import Optional

from .extractor import SubmissionExtractResult, combined_extract_text

logger = logging.getLogger(__name__)

EMPTY_SUBMISSION_PLACEHOLDER = '(No extractable student content.)'


def _submission_body_looks_like_single_python_module(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return False
    return bool(re.search(r'^\s*(def |class |import |from \w+ import )', text, re.MULTILINE))


def _should_check_python_syntax_for_submission(submission, extract_body: str) -> bool:
    if submission.assignment.project_template.submission_type != 'CODE':
        return False
    if _submission_body_looks_like_single_python_module(extract_body):
        return True
    notes_or_text = (submission.submission_text or '').strip()
    if notes_or_text and _submission_body_looks_like_single_python_module(notes_or_text):
        return True
    return False


def get_python_syntax_rejection_message_or_none(
    submission, extract: SubmissionExtractResult
) -> Optional[str]:
    """Parse as one module when the flattened text looks like plain Python; skip multi-file markers."""
    body = combined_extract_text(extract)
    if '===== FILE:' in body:
        return None
    if not _should_check_python_syntax_for_submission(submission, body):
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


def is_submission_text_bundle_empty(body: str) -> bool:
    """Nothing to send to the model or plagiarism text scan."""
    stripped = (body or '').strip()
    return not stripped or stripped == EMPTY_SUBMISSION_PLACEHOLDER
