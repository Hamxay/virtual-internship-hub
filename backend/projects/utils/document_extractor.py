"""Extract text from supported local file paths for FR4 evaluation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BINARY_SUFFIXES = frozenset({'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.gif'})


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
        - ``.pdf`` / images: note binary artifact presence in text.
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
            if suffix in BINARY_SUFFIXES:
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

