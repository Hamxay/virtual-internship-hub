"""
FR7 career coach: context injection (RAG-style grounding) for Gemini.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple

from django.conf import settings

from accounts.models import StudentProfile
from projects.models import ProjectSubmission

if TYPE_CHECKING:
    from accounts.models import User

logger = logging.getLogger(__name__)

CHAT_GEMINI_MODEL = 'gemini-1.5-flash'


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
- Keep tone supportive, concise, and actionable; no shame; age-appropriate professional language.
"""

    return f"""You are the Virtual Internship Hub **AI Career Coach** (Gemini 1.5 Flash).

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


def run_career_coach_gemini(system_instruction: str, history: List[Tuple[str, str]]) -> str:
    """
    Call Gemini with a fixed system instruction and short in-session memory.

    ``history`` is chronological (oldest first): list of (role, content) with role in
    {'user', 'model'}.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not str(api_key).strip():
        raise RuntimeError('GEMINI_API_KEY is not configured.')

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError('google-generativeai is not installed.') from exc

    lines = []
    for role, text in history:
        label = 'User' if role == 'user' else 'Coach'
        lines.append(f'{label}: {text}')
    transcript = '\n\n'.join(lines) if lines else '(no prior messages in this window)'

    user_prompt = (
        'Below is the recent conversation (most recent messages may be at the end). '
        'Reply as the Career Coach to the latest user turn.\n\n'
        f'{transcript}'
    )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        CHAT_GEMINI_MODEL,
        system_instruction=system_instruction,
    )
    response = model.generate_content(user_prompt)
    try:
        raw_text = response.text
    except ValueError as exc:
        logger.warning('Gemini career coach returned no text: %s', exc)
        raise RuntimeError('Gemini returned no text (blocked or empty response).') from exc
    if not raw_text or not raw_text.strip():
        raise RuntimeError('Empty response from Gemini.')
    return raw_text.strip()
