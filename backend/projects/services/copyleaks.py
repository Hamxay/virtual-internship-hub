from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CopyleaksSubmitResult:
    submitted: bool
    scan_id: str | None = None
    error: str | None = None


def is_copyleaks_enabled() -> bool:
    email = str(getattr(settings, 'COPYLEAKS_EMAIL', '') or '').strip()
    api_key = str(getattr(settings, 'COPYLEAKS_API_KEY', '') or '').strip()
    webhook_base = str(getattr(settings, 'COPYLEAKS_WEBHOOK_BASE_URL', '') or '').strip()
    return bool(email and api_key and webhook_base)


def _status_webhook_url(submission_id: int) -> str:
    base = str(getattr(settings, 'COPYLEAKS_WEBHOOK_BASE_URL', '') or '').strip().rstrip('/')
    if not base:
        return ''
    return f'{base}/api/projects/copyleaks/webhook/{{STATUS}}/{submission_id}/'


def submit_text_scan(submission_id: int, text: str) -> CopyleaksSubmitResult:
    if not is_copyleaks_enabled():
        return CopyleaksSubmitResult(
            submitted=False,
            error='Copyleaks disabled (COPYLEAKS_EMAIL/API_KEY/WEBHOOK_BASE_URL missing).',
        )

    email = str(getattr(settings, 'COPYLEAKS_EMAIL', '') or '').strip()
    api_key = str(getattr(settings, 'COPYLEAKS_API_KEY', '') or '').strip()
    webhook = _status_webhook_url(submission_id)
    if not webhook:
        return CopyleaksSubmitResult(submitted=False, error='COPYLEAKS_WEBHOOK_BASE_URL is empty.')

    try:
        from copyleaks.copyleaks import Copyleaks
        from copyleaks.exceptions.command_error import CommandError
        from copyleaks.models.submit.document import FileDocument
        from copyleaks.models.submit.properties.ai_generated_text import AIGeneratedText
        from copyleaks.models.submit.properties.scan_properties import ScanProperties
    except Exception as exc:
        return CopyleaksSubmitResult(submitted=False, error=f'Copyleaks SDK import failed: {exc}')

    client = Copyleaks()
    encoded_text = base64.b64encode((text or '').encode('utf-8')).decode('utf-8')
    scan_id = str(submission_id)

    try:
        auth_token = client.login(email, api_key)
        scan_properties = ScanProperties(webhook)
        ai_generated_text = AIGeneratedText()
        ai_generated_text.set_detect(True)
        scan_properties.set_ai_generated_text(ai_generated_text)

        document = FileDocument(encoded_text, f'submission-{submission_id}.txt')
        document.set_properties(scan_properties)

        logger.info(
            'Copyleaks submit payload submission=%s scan_id=%s ai_detect=%s webhook=%s',
            submission_id,
            scan_id,
            True,
            webhook,
        )
        client.submit_file(auth_token, scan_id, document)
        logger.info(
            'Copyleaks submit success submission=%s scan_id=%s webhook=%s',
            submission_id,
            scan_id,
            webhook,
        )
        return CopyleaksSubmitResult(submitted=True, scan_id=scan_id, error=None)
    except CommandError as exc:
        logger.exception('Copyleaks command error submission=%s: %s', submission_id, exc)
        return CopyleaksSubmitResult(submitted=False, error=str(exc))
    except Exception as exc:
        logger.exception('Copyleaks submit failed submission=%s: %s', submission_id, exc)
        return CopyleaksSubmitResult(submitted=False, error=str(exc))


def extract_similarity_percent(payload: dict[str, Any]) -> float | None:
    values: list[float] = []

    def _coerce(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number < 0 or number > 100:
            return None
        return number

    target_keys = {
        'aggregatedscore',
        'totalscore',
        'similarity',
        'similarityscore',
        'matchscore',
        'identicalpercent',
        'percent',
        'score',
    }

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_norm = str(key).lower().replace('_', '').replace('-', '')
                if key_norm in target_keys:
                    score = _coerce(value)
                    if score is not None:
                        values.append(score)
                _walk(value)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload or {})
    if not values:
        return None
    return round(max(values), 2)
