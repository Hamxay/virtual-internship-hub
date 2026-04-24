"""
Lightweight career-coach scope checks (server-side).

Blocks obvious biography / trivia / coding-help prompts before calling OpenRouter when
the message has no career-related cues—reduces reliance on the model obeying system text alone.
"""

from __future__ import annotations

# If any of these appear, we let the message through to the LLM (even if it also has "who is").
_CAREER_HINT_SUBSTRINGS: tuple[str, ...] = (
    'intern',
    'internship',
    'career',
    'resume',
    'cv',
    'portfolio',
    'job',
    'interview',
    'skill',
    'project',
    'domain',
    'mentor',
    'assignment',
    'upwork',
    'freelance',
    'study',
    'degree',
    'linkedin',
    'application',
    'company',
    'role',
    'goal',
    'learn',
    'placement',
    'opportunity',
    'experience',
    'course',
    'university',
    'graduate',
    'network',
    'salary',
    'offer',
    'reference',
    'cover letter',
    'vacancy',
    'recruit',
    'candidate',
    'hub',
    'coach',
)

# Biography / trivia style openers with no career link → canned refusal.
_BLOCKED_PREFIXES: tuple[str, ...] = (
    'who is ',
    'who are ',
    'who was ',
    'who were ',
    'what is the capital of ',
    'when did world war',
    'when was world war',
)

_CODING_HELP_PREFIXES: tuple[str, ...] = (
    'write a python',
    'write a java',
    'write a javascript',
    'write a sql',
    'debug my',
    'fix this code',
    'explain this code',
    'leetcode',
)

OFF_SCOPE_COACH_REPLY = (
    "I'm only your **career and internship coach** for Virtual Internship Hub—things like "
    "goals, skills, projects, applications, and portfolio. I can't help with that topic here. "
    "What are you trying to achieve in your studies or job search right now?"
)


def user_message_in_career_scope(text: str) -> bool:
    """
    Return True if the user message should be sent to the LLM.

    Heuristic: if there is no obvious career/internship cue and the message looks like
    biography/trivia or direct coding help, treat as out of scope.
    """
    raw = (text or '').strip()
    if not raw:
        return False
    low = raw.lower()

    if any(hint in low for hint in _CAREER_HINT_SUBSTRINGS):
        return True

    for prefix in _BLOCKED_PREFIXES:
        if low.startswith(prefix):
            return False

    head = low[:120]
    for prefix in _CODING_HELP_PREFIXES:
        if prefix in head:
            return False

    return True
