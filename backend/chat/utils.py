"""
FR7 career coach: context injection (RAG-style grounding).
Chat completions use **OpenRouter** only. FR4 project evaluation uses Gemini in ``projects``.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple

import requests
from django.conf import settings

from accounts.models import StudentProfile
from projects.models import ProjectSubmission

if TYPE_CHECKING:
    from accounts.models import User

logger = logging.getLogger(__name__)


def _student_domains(user: 'User') -> list[str]:
    profile = StudentProfile.objects.filter(user=user).first()
    if not profile:
        return []
    return list(profile.target_domains.values_list('name', flat=True))


def _completed_project_titles(user: 'User', limit: int = 8) -> list[str]:
    """Completed internship projects: assignment COMPLETED + linked submission exists."""
    qs = (
        ProjectSubmission.objects.filter(
            assignment__status='COMPLETED',
            assignment__student=user,
        )
        .select_related('assignment__project_template')
        .order_by('-submitted_at', '-id')[:limit]
    )
    titles = []
    for sub in qs:
        tpl = sub.assignment.project_template
        titles.append(tpl.title if tpl else f'Submission {sub.pk}')
    return titles


def build_career_coach_prompt(user: 'User') -> str:
    """
    Build system-style instructions from the learner's profile and progress.

    Three-tier state:
      1 — Blank: no domains, no completed projects → onboarding & path choice.
      2 — Theorist: domains set, no completed projects → motivate first assignment.
      3 — Practitioner: at least one completed project → monetization, Upwork,
         and linking to their FR6 public portfolio.
    """
    domains = _student_domains(user)
    project_titles = _completed_project_titles(user)
    has_domains = bool(domains)
    has_completed_projects = bool(project_titles)

    if has_completed_projects:
        state_label = 'STATE 3 — Practitioner'
        focus = (
            'Prioritize freelancing monetization, Upwork-style positioning and proposals, '
            'client communication, pricing and packaging offers, and how to reference their '
            'completed work. Strongly encourage them to maintain and share their FR6 public '
            f'portfolio (API path pattern: /api/portfolio/{user.username}/ for their public showcase).'
        )
    elif has_domains:
        state_label = 'STATE 2 — Theorist'
        focus = (
            'They have chosen direction (domains) but have not finished a project here yet. '
            'Motivate them to start their first assignment: small steps, time-boxing, '
            'overcoming procrastination, and connecting domain interest to concrete deliverables.'
        )
    else:
        state_label = 'STATE 1 — Blank'
        focus = (
            'They have not selected domains and have no completed projects in this platform. '
            'Guide onboarding: clarify goals, explore career directions, and help them choose '
            'initial domains or learning paths before deep project work.'
        )

    domains_line = ', '.join(domains) if domains else '(none selected)'
    projects_line = '; '.join(project_titles) if project_titles else '(none completed yet)'

    guardrails = """
## Non-negotiable guardrails (deny and pivot)
- You are a **career and internship coach only**. You do **not** write, debug, or explain code,
  scripts, SQL, regex, shell commands, or technical implementation steps for software.
- Do **not** tutor on computer science theory, LeetCode-style algorithms, or toolchain setup
  unless framed purely as high-level study habits (still no code).
- If the user asks for coding, debugging, homework solutions, or unrelated topics (medical,
  legal, politics, personal therapy, etc.), **briefly refuse** and **pivot** back to career
  development, internships, motivation, or portfolio/Upwork positioning aligned with their state.
- Do **not** answer biography or general-knowledge questions about public figures, history,
  geography, or current events unless the user clearly ties them to **their own** career,
  internship, or learning goals in this platform.
- Keep tone supportive, concise, and actionable; no shame; age-appropriate professional language.
"""

    return f"""You are the Virtual Internship Hub **AI Career Coach**.

## Learner context (grounding — treat as facts for this user)
- Username: {user.username}
- Selected domains: {domains_line}
- Completed projects (assignment status COMPLETED): {projects_line}

## Coaching state
- {state_label}
- Coaching focus: {focus}

{guardrails}

## Session behavior
- Stay within the focus for this state while personalizing to their domains and completed projects.
- If context is sparse, ask clarifying questions about goals, constraints, and timeline.
- Never fabricate completed projects or domains; only use what is listed above.
"""


def _openrouter_role(role: str) -> str:
    if role == 'user':
        return 'user'
    return 'assistant'


def _openrouter_choice_text(message: dict) -> str:
    """Normalize ``choices[0].message.content`` (string or multimodal parts list)."""
    content = message.get('content')
    if content is None:
        return ''
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get('type') == 'text' and isinstance(part.get('text'), str):
                    parts.append(part['text'])
                elif isinstance(part.get('text'), str):
                    parts.append(part['text'])
            elif isinstance(part, str):
                parts.append(part)
        return ''.join(parts).strip()
    return str(content).strip()


def _run_career_coach_openrouter(system_instruction: str, history: List[Tuple[str, str]]) -> str:
    """OpenAI-compatible chat completions (OpenRouter)."""
    api_key = (getattr(settings, 'OPENROUTER_API_KEY', None) or '').strip()
    if not api_key:
        raise RuntimeError('OPENROUTER_API_KEY is not configured.')

    base = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
    model_id = (getattr(settings, 'OPENROUTER_CHAT_MODEL', None) or '').strip()
    if not model_id:
        raise RuntimeError('OPENROUTER_CHAT_MODEL is not set.')

    messages = [{'role': 'system', 'content': system_instruction}]
    for role, text in history:
        messages.append({'role': _openrouter_role(role), 'content': text or ''})

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    referer = (getattr(settings, 'OPENROUTER_HTTP_REFERER', None) or '').strip()
    if referer:
        headers['HTTP-Referer'] = referer
    title = (getattr(settings, 'OPENROUTER_APP_TITLE', None) or '').strip()
    if title:
        # OpenRouter accepts X-Title; docs also recommend X-OpenRouter-Title for attribution.
        headers['X-Title'] = title
        headers['X-OpenRouter-Title'] = title

    url = f'{base}/chat/completions'
    payload = {
        'model': model_id,
        'messages': messages,
        'temperature': 0.7,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=(15, 120))
    except requests.RequestException as exc:
        logger.warning('OpenRouter career coach request failed: %s', exc)
        raise RuntimeError('Could not reach OpenRouter (network error).') from exc

    if resp.status_code == 401:
        raise RuntimeError('OpenRouter rejected the API key (401).')
    if resp.status_code == 402:
        raise RuntimeError('OpenRouter: insufficient credits or quota (402). Add credits or check your plan.')
    if resp.status_code == 429:
        raise RuntimeError('OpenRouter rate limit exceeded; try again shortly.')

    try:
        data = resp.json()
    except ValueError:
        logger.warning('OpenRouter non-JSON response status=%s body=%s', resp.status_code, resp.text[:500])
        raise RuntimeError('OpenRouter returned an invalid response.') from None

    if resp.status_code >= 400:
        err = data.get('error') if isinstance(data, dict) else None
        msg = err.get('message', resp.text[:300]) if isinstance(err, dict) else str(data)[:300]
        raise RuntimeError(f'OpenRouter error ({resp.status_code}): {msg}')

    choices = data.get('choices') if isinstance(data, dict) else None
    if not choices:
        raise RuntimeError('OpenRouter returned no choices.')
    message = choices[0].get('message') if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise RuntimeError('OpenRouter returned an unexpected choice shape.')
    raw_text = _openrouter_choice_text(message)
    if not raw_text:
        raise RuntimeError('Empty response from OpenRouter.')
    return raw_text


def run_career_coach(system_instruction: str, history: List[Tuple[str, str]]) -> str:
    """
    Career coach reply via OpenRouter (``OPENROUTER_API_KEY`` / ``OPENROUTER_CHAT_MODEL``).

    ``history`` is chronological (oldest first): (role, content) with role in {'user', 'model'}.
    """
    return _run_career_coach_openrouter(system_instruction, history)

