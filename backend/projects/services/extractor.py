"""
FR4 — Extract text or local file paths from student submissions for AI evaluation.

- ``.docx``: paragraph text via python-docx.
- ``.xlsx``: sheet data as CSV-like string via pandas/openpyxl.
- GitHub ``repository_url``: normalize blob URLs to raw.githubusercontent.com and GET text.
- ``.pdf`` / common images: no text extraction here; return a local path marker for binary artifacts.
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

import requests

logger = logging.getLogger(__name__)

# Binary extensions kept as local path references.
BINARY_DIRECT_UPLOAD_SUFFIXES = frozenset({
    '.pdf',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
})

REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class SubmissionExtractResult:
    """Structured payload for the evaluator (text for the prompt + optional local paths)."""

    text_parts: List[str] = field(default_factory=list)
    """Human-readable fragments concatenated into the LLM prompt."""

    binary_local_paths: List[str] = field(default_factory=list)
    """Absolute paths for binary artifacts (PDF / images)."""


def _append_text(result: SubmissionExtractResult, label: str, body: str) -> None:
    cleaned = (body or '').strip()
    if cleaned:
        result.text_parts.append(f'### {label}\n{cleaned}')


def github_url_to_raw_content(url: str) -> str:
    """
    Fetch text from a GitHub URL.

    - ``/blob/`` links are rewritten to ``raw.githubusercontent.com``.
    - Bare repo URLs attempt ``README.md`` on ``main`` then ``master``.
    """
    if not url or not url.strip():
        return ''

    normalized = url.strip()
    blob_match = re.match(
        r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)',
        normalized,
        re.IGNORECASE,
    )
    if blob_match:
        org, repo, branch, path = blob_match.groups()
        path = unquote(path)
        raw_url = f'https://raw.githubusercontent.com/{org}/{repo}/{branch}/{path}'
    elif re.match(r'https?://github\.com/[^/]+/[^/]+/?$', normalized.rstrip('/')):
        parts = normalized.rstrip('/').split('/')
        org, repo = parts[-2], parts[-1].removesuffix('.git')
        for branch in ('main', 'master'):
            raw_url = f'https://raw.githubusercontent.com/{org}/{repo}/{branch}/README.md'
            try:
                response = requests.get(raw_url, timeout=REQUEST_TIMEOUT_SECONDS)
                if response.ok:
                    return response.text
            except requests.RequestException as exc:
                logger.warning('GitHub README fetch failed (%s): %s', raw_url, exc)
        return ''
    else:
        raw_url = normalized

    try:
        response = requests.get(raw_url, timeout=REQUEST_TIMEOUT_SECONDS)
        if not response.ok:
            logger.warning('HTTP %s fetching %s', response.status_code, raw_url)
            return ''
        return response.text
    except requests.RequestException as exc:
        logger.warning('Request failed for %s: %s', raw_url, exc)
        return ''


def extract_text_from_docx(file_field) -> str:
    """Return concatenated paragraph text from a Word document."""
    try:
        from docx import Document
    except ImportError:
        logger.warning('python-docx not installed; skipping DOCX extraction.')
        return ''

    try:
        file_field.open('rb')
        data = file_field.read()
    finally:
        try:
            file_field.close()
        except Exception:
            pass

    document = Document(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
    return '\n'.join(paragraphs)


def extract_text_from_xlsx(file_field) -> str:
    """Render spreadsheet(s) as CSV-like strings."""
    try:
        import pandas as pd
    except ImportError:
        logger.warning('pandas not installed; skipping XLSX extraction.')
        return ''

    try:
        file_field.open('rb')
        data = file_field.read()
    finally:
        try:
            file_field.close()
        except Exception:
            pass

    buffer = io.BytesIO(data)
    try:
        workbook = pd.read_excel(buffer, sheet_name=None, engine='openpyxl')
    except Exception as exc:
        logger.warning('XLSX parse failed: %s', exc)
        return ''

    chunks: List[str] = []
    for sheet_name, frame in workbook.items():
        csv_string = frame.to_csv(index=False)
        chunks.append(f'## Sheet: {sheet_name}\n{csv_string}')
    return '\n\n'.join(chunks)


def combined_extract_text(extract: SubmissionExtractResult) -> str:
    """Single string of all text parts (for gatekeepers / similarity)."""
    return '\n\n'.join(extract.text_parts or []).strip()


def resolve_local_path(file_field) -> Optional[str]:
    """Absolute path for an on-disk uploaded file, if available."""
    if not file_field:
        return None
    try:
        name = file_field.name
    except Exception:
        return None
    if not name:
        return None
    path = Path(file_field.path)
    if path.is_file():
        return str(path)
    return None


def extract_submission_for_evaluation(submission) -> SubmissionExtractResult:
    """
    Build prompt text and optional binary artifact paths from a ``ProjectSubmission``.

    Expects ``submission.assignment`` and ``project_template`` to be usable (caller
    should ``select_related`` / ``prefetch_related`` as needed).
    """
    result = SubmissionExtractResult()
    template = submission.assignment.project_template
    submission_type = template.submission_type

    _append_text(result, 'Submission notes', submission.notes or '')
    _append_text(result, 'Submission text', submission.submission_text or '')

    repository_url = (submission.repository_url or '').strip()
    if repository_url and 'github.com' in repository_url.lower():
        repo_body = github_url_to_raw_content(repository_url)
        _append_text(result, 'Repository / GitHub content', repo_body)
    elif repository_url:
        _append_text(result, 'Repository URL', repository_url)

    uploaded = submission.uploaded_file
    if not uploaded or not uploaded.name:
        return result

    suffix = Path(uploaded.name).suffix.lower()
    if suffix == '.docx' or submission_type == 'WORD':
        doc_text = extract_text_from_docx(uploaded)
        _append_text(result, 'Uploaded Word document', doc_text)
    elif suffix in ('.xlsx', '.xls') or submission_type == 'SPREADSHEET':
        sheet_text = extract_text_from_xlsx(uploaded)
        _append_text(result, 'Uploaded spreadsheet', sheet_text)
    elif suffix in BINARY_DIRECT_UPLOAD_SUFFIXES or submission_type in ('PDF', 'DESIGN'):
        local_path = resolve_local_path(uploaded)
        if local_path:
            result.binary_local_paths.append(local_path)
        else:
            _append_text(result, 'Uploaded file', f'(Binary file: {uploaded.name}; path not on local disk.)')
    else:
        local_path = resolve_local_path(uploaded)
        if local_path and suffix in BINARY_DIRECT_UPLOAD_SUFFIXES:
            result.binary_local_paths.append(local_path)
        else:
            _append_text(
                result,
                'Uploaded file',
                f'Unsupported extension for text extraction: {suffix or "unknown"}',
            )

    return result
