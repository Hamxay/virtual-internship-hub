"""OpenRouter multimodal (vision) pass for DESIGN template submissions with image uploads."""
from __future__ import annotations

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DESIGN_IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.gif'})

_MAX_LONG_EDGE = 2048
_JPEG_QUALITY = 85
_MAX_JPEG_BYTES = 4 * 1024 * 1024

_OPENROUTER_VISION_SYSTEM_PROMPT = (
    'You are a senior UI/UX and graphic design mentor. You are shown one student deliverable image. '
    'Describe what is visible factually (layout, hierarchy, typography, color, spacing, components, '
    'affordances, obvious states). Note strengths and concrete improvements for clarity, consistency, '
    'and basic accessibility (contrast, touch targets, labels). '
    'Do not invent features not visible. If the image is unclear, say so. '
    'Reply with plain prose only — no JSON, no markdown code fences.'
)

# Free tier: OpenRouter picks a capable free model (including vision when you send images).
# Override with OPENROUTER_VISION_MODEL e.g. google/gemma-3-27b-it:free or a specific VL model id.
_DEFAULT_OPENROUTER_VISION_MODEL = 'openrouter/free'


def resolve_openrouter_vision_model_id() -> str:
    configured = (getattr(settings, 'OPENROUTER_VISION_MODEL', None) or '').strip()
    if configured:
        return configured
    return _DEFAULT_OPENROUTER_VISION_MODEL


def _format_project_template_context_for_vision_user_prompt(template: Any) -> str:
    instruction = getattr(template, 'instruction', None)
    lines = [
        f'**Project title:** {template.title}',
        f'**Short description:** {getattr(template, "short_description", "") or ""}',
        f'**Business problem:** {getattr(template, "business_problem", "") or ""}',
    ]
    if instruction:
        lines.append(f'**Instruction overview:** {instruction.overview or ""}')
        lines.append(f'**Deliverables:** {json.dumps(instruction.deliverables or [], indent=2)}')
        lines.append(f'**Steps:** {json.dumps(instruction.steps or [], indent=2)}')
        lines.append(f'**Evaluation notes:** {instruction.evaluation_notes or ""}')
    return '\n'.join(lines)


def _prepare_local_image_as_jpeg_data_url(path: Path) -> Optional[str]:
    try:
        from PIL import Image
    except ImportError:
        logger.warning('Pillow not available; cannot prepare design image for vision.')
        return None

    try:
        with Image.open(path) as im:
            if getattr(im, 'n_frames', 1) > 1:
                im.seek(0)
            if im.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', im.size, (255, 255, 255))
                rgba = im.convert('RGBA')
                background.paste(rgba, mask=rgba.split()[-1])
                im = background
            elif im.mode == 'P':
                im = im.convert('RGBA')
                background = Image.new('RGB', im.size, (255, 255, 255))
                background.paste(im, mask=im.split()[-1])
                im = background
            elif im.mode != 'RGB':
                im = im.convert('RGB')

            w, h = im.size
            long_edge = max(w, h)
            if long_edge > _MAX_LONG_EDGE:
                scale = _MAX_LONG_EDGE / long_edge
                im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

            for q in (_JPEG_QUALITY, 72, 55):
                buf = io.BytesIO()
                im.save(buf, format='JPEG', quality=q, optimize=True)
                raw = buf.getvalue()
                if len(raw) <= _MAX_JPEG_BYTES or q == 55:
                    break
            if len(raw) > _MAX_JPEG_BYTES:
                logger.warning('Design vision: JPEG still large (%s bytes) for %s', len(raw), path.name)
            b64 = base64.standard_b64encode(raw).decode('ascii')
            return f'data:image/jpeg;base64,{b64}'
    except Exception as exc:
        logger.warning('Design vision: image prep failed for %s: %s', path, exc)
        return None


def _string_from_chat_completion_message(message: dict) -> str:
    content = message.get('content')
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                parts.append(item['text'])
            elif isinstance(item, str):
                parts.append(item)
        return ''.join(parts).strip()
    return str(content or '').strip()


def build_design_submission_vision_markdown(file_path: str, template: Any) -> Optional[str]:
    """
    Call OpenRouter chat completions with an image + text. Returns markdown for the evaluation
    bundle, or None on skip / failure (caller falls back to document placeholder text).
    """
    api_key = (getattr(settings, 'OPENROUTER_API_KEY', '') or '').strip()
    if not api_key:
        return None

    path = Path(file_path)
    if not path.is_file():
        return None

    suffix = path.suffix.lower()
    if suffix not in DESIGN_IMAGE_SUFFIXES:
        return None

    image_data_url = _prepare_local_image_as_jpeg_data_url(path)
    if not image_data_url:
        return None

    base = (getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1') or '').rstrip('/')
    model_id = resolve_openrouter_vision_model_id()
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

    user_text = (
        '## Assignment context (for grounding)\n\n'
        f'{_format_project_template_context_for_vision_user_prompt(template)}\n\n'
        '## Task\n'
        'Review the attached student design image against the assignment context. '
        'Write 4–10 short paragraphs of feedback a mentor could use. '
        'Start with a brief factual summary of what appears on screen, then strengths, then improvements.'
    )

    payload = {
        'model': model_id,
        'temperature': 0.2,
        'max_tokens': 1800,
        'messages': [
            {'role': 'system', 'content': _OPENROUTER_VISION_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': user_text},
                    {'type': 'image_url', 'image_url': {'url': image_data_url}},
                ],
            },
        ],
    }

    try:
        response = requests.post(
            f'{base}/chat/completions',
            headers=headers,
            json=payload,
            timeout=(15, 90),
        )
    except requests.RequestException as exc:
        logger.warning('Design vision: network error: %s', exc)
        return None

    try:
        data = response.json()
    except ValueError:
        logger.warning('Design vision: non-JSON response status=%s', response.status_code)
        return None

    if response.status_code >= 400:
        err = data.get('error') if isinstance(data, dict) else None
        msg = err.get('message') if isinstance(err, dict) else str(data)
        logger.warning('Design vision: API error (%s): %s', response.status_code, msg)
        return None

    choices = data.get('choices') if isinstance(data, dict) else None
    if not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get('message')
    if not isinstance(message, dict):
        return None
    raw = _string_from_chat_completion_message(message)
    if not raw:
        return None
    raw = re.sub(r'```[\s\S]*?```', '', raw).strip()
    if not raw:
        return None

    header = '## Automated visual analysis (model-assisted)\n\n'
    body = raw[:24_000] + ('…' if len(raw) > 24_000 else '')
    return header + body
