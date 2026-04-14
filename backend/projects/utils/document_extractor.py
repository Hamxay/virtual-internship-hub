"""Extract text or upload binaries for Gemini from a local file path."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_BINARY_SUFFIXES = frozenset({'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.gif'})


@dataclass
class DocumentExtractOutcome:
    """Text for the prompt plus optional native Gemini uploads (PDF / images)."""

    text_markdown: Optional[str] = None
    gemini_file_handles: List[Any] = field(default_factory=list)


class UniversalDocumentExtractor:
    @staticmethod
    def process(file_path: str) -> DocumentExtractOutcome:
        """
        Process a document at ``file_path``.

        - ``.csv`` / ``.xlsx`` / ``.xls``: first 100 rows as a Markdown-like table.
        - ``.docx``: paragraph text.
        - ``.pdf`` / images: ``google.generativeai.upload_file``; handle list in ``gemini_file_handles``.
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        outcome = DocumentExtractOutcome()

        if not path.is_file():
            logger.warning('DocumentExtractor: missing file %s', file_path)
            return outcome

        try:
            if suffix == '.csv':
                outcome.text_markdown = UniversalDocumentExtractor._csv_to_markdown(path)
                return outcome
            if suffix in ('.xlsx', '.xls'):
                outcome.text_markdown = UniversalDocumentExtractor._excel_to_markdown(path, suffix)
                return outcome
            if suffix == '.docx':
                outcome.text_markdown = UniversalDocumentExtractor._docx_to_text(path)
                return outcome
            if suffix in GEMINI_BINARY_SUFFIXES:
                UniversalDocumentExtractor._attach_gemini_upload(path, outcome)
                return outcome

            logger.info('DocumentExtractor: unsupported extension %s for %s', suffix, file_path)
        except Exception as exc:
            logger.exception('DocumentExtractor failed for %s: %s', file_path, exc)

        return outcome

    @staticmethod
    def _csv_to_markdown(path: Path) -> str:
        import pandas as pd

        frame = pd.read_csv(path, nrows=100)
        return UniversalDocumentExtractor._frame_to_markdown(frame, path.name)

    @staticmethod
    def _excel_to_markdown(path: Path, suffix: str) -> str:
        import pandas as pd

        engine = 'openpyxl' if suffix == '.xlsx' else None
        frame = pd.read_excel(path, sheet_name=0, nrows=100, engine=engine)
        return UniversalDocumentExtractor._frame_to_markdown(frame, path.name)

    @staticmethod
    def _frame_to_markdown(frame, label: str) -> str:
        try:
            body = frame.to_markdown(index=False)
        except Exception:
            body = frame.to_csv(index=False)
        return f'## Spreadsheet: {label}\n\n{body}'

    @staticmethod
    def _docx_to_text(path: Path) -> str:
        from docx import Document

        document = Document(str(path))
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
        return '\n'.join(paragraphs)

    @staticmethod
    def _attach_gemini_upload(path: Path, outcome: DocumentExtractOutcome) -> None:
        api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
        if not str(api_key).strip():
            logger.warning('DocumentExtractor: GEMINI_API_KEY missing; cannot upload %s', path)
            return
        try:
            import google.generativeai as genai
        except ImportError:
            logger.warning('google-generativeai not installed; cannot upload %s', path)
            return

        try:
            genai.configure(api_key=api_key)
            handle = genai.upload_file(str(path), mime_type=_guess_mime(path.suffix))
            outcome.gemini_file_handles.append(handle)
        except Exception as exc:
            logger.exception('Gemini upload_file failed for %s: %s', path, exc)


def _guess_mime(suffix: str) -> str:
    mapping = {
        '.pdf': 'application/pdf',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    return mapping.get(suffix.lower(), 'application/octet-stream')
