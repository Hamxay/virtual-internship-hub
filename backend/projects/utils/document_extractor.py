"""Extract text from local uploads for the evaluation pipeline."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Images: no text extraction; PDF handled separately.
IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.gif'})

MAX_PDF_PAGES = 40
MAX_PDF_CHARS = 100_000


@dataclass
class DocumentExtractOutcome:
    """Text for the prompt."""

    text_markdown: Optional[str] = None


class UniversalDocumentExtractor:
    @staticmethod
    def process(file_path: str) -> DocumentExtractOutcome:
        """
        Process a document at ``file_path``.

        - ``.csv`` / ``.xlsx`` / ``.xls``: first 100 rows as a Markdown-like table.
        - ``.docx``: paragraph text.
        - ``.pdf``: extract text with pypdf (page/character caps).
        - images: note binary artifact presence in text.
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
            if suffix == '.pdf':
                outcome.text_markdown = UniversalDocumentExtractor._pdf_to_text(path)
                return outcome
            if suffix in IMAGE_SUFFIXES:
                outcome.text_markdown = (
                    f'## Binary artifact received: {path.name}\n\n'
                    'Binary file content is not directly extractable. '
                    'Evaluation will rely on notes/submission text and other extracted artifacts.'
                )
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
    def _pdf_to_text(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning('pypdf not installed; skipping PDF text extraction for %s', path.name)
            return (
                f'## PDF: {path.name}\n\n'
                '(PDF text extraction is unavailable on this server.)'
            )

        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            logger.warning('PdfReader failed for %s: %s', path, exc)
            return f'## PDF: {path.name}\n\n(Could not open PDF: {exc})'

        if reader.is_encrypted:
            try:
                reader.decrypt('')
            except Exception:
                return f'## PDF: {path.name}\n\n(PDF is password-protected; text was not extracted.)'

        pages = reader.pages
        parts: list[str] = []
        total_chars = 0
        truncated = False
        for i, page in enumerate(pages[:MAX_PDF_PAGES]):
            try:
                raw = page.extract_text() or ''
            except Exception as exc:
                logger.debug('PDF page %s extract failed: %s', i, exc)
                continue
            chunk = raw.strip()
            if not chunk:
                continue
            remaining = MAX_PDF_CHARS - total_chars
            if remaining <= 0:
                truncated = True
                break
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
                truncated = True
            parts.append(chunk)
            total_chars += len(chunk)
            if truncated:
                break

        body = '\n\n'.join(parts).strip()
        extra_pages = len(pages) - min(len(pages), MAX_PDF_PAGES)
        notes: list[str] = []
        if extra_pages > 0:
            notes.append(f'{extra_pages} additional page(s) not scanned (limit {MAX_PDF_PAGES}).')
        if truncated:
            notes.append('Content truncated to character limit for evaluation.')

        if not body:
            return (
                f'## PDF: {path.name}\n\n'
                '(No extractable text; the file may be scanned/image-only or use an unsupported layout.)'
            )
        suffix = '\n\n' + ' '.join(notes) if notes else ''
        return f'## PDF: {path.name}\n\n{body}{suffix}'

