"""Build system + user prompts for automated project grading (per submission type)."""
from __future__ import annotations

import json
import re
from typing import Any

from projects.services.evaluation_gatekeepers import EMPTY_SUBMISSION_PLACEHOLDER

EMPTY_CONTENT_MARKER = EMPTY_SUBMISSION_PLACEHOLDER

_CODE_SYSTEM = (
    'You are a Senior Software Engineer and Technical Mentor evaluating a student code project.\n'
    'Assess code quality, correctness, structure, and how well the student meets the deliverables.\n'
    'Look at repository structure, naming conventions, logic, completeness, and edge-case handling — not just syntax.\n'
    'Be specific: reference file names, function names, or code patterns when giving feedback.\n'
    'Respond with strictly valid raw JSON only — no markdown fences, no commentary.'
)

_DOCUMENT_SYSTEM = (
    'You are a Senior Technical Mentor evaluating a student written project deliverable.\n'
    'Assess clarity, completeness, correctness, and how well the submission meets the stated deliverables.\n'
    'Be specific: point out which sections are strong or need improvement.\n'
    'Respond with strictly valid raw JSON only — no markdown fences, no commentary.'
)

_BINARY_SYSTEM = (
    'You are a Senior Technical Mentor. The student submitted a binary file (PDF or image) '
    'which cannot be read as text.\n'
    'Evaluate using only the written notes and submission text provided below — the file content is not available.\n'
    'Score conservatively and clearly state in your improvements that the binary file content could not be assessed.\n'
    'Respond with strictly valid raw JSON only — no markdown fences, no commentary.'
)

_DESIGN_VISION_SYSTEM = (
    'You are a Senior Technical Mentor evaluating a UI/UX or graphic design submission.\n'
    'The student content includes an **Automated visual analysis** section produced by a vision model from their image. '
    'Use that analysis together with their notes and submission text. '
    'Judge alignment with deliverables, clarity, and professionalism; be specific in your feedback.\n'
    'If the automated analysis conflicts with written requirements, weight the assignment context and written rationale.\n'
    'Respond with strictly valid raw JSON only — no markdown fences, no commentary.'
)

_DEFAULT_SYSTEM = (
    'You are a Senior Technical Mentor evaluating a student project submission.\n'
    'You must be fair, specific, and constructive. Base every judgment only on the '
    'assignment context and the student content provided in the user message.\n'
    'Respond with strictly valid raw JSON only — no markdown fences, no commentary.'
)


VISION_ANALYSIS_MARKER = '## Automated visual analysis (model-assisted)'


def _system_for_type(submission_type: str, student_content: str = '') -> str:
    t = (submission_type or '').upper().strip()
    if t == 'CODE':
        return _CODE_SYSTEM
    if t in ('DOCUMENT', 'WORD', 'SPREADSHEET'):
        return _DOCUMENT_SYSTEM
    if t == 'DESIGN' and VISION_ANALYSIS_MARKER in (student_content or ''):
        return _DESIGN_VISION_SYSTEM
    if t in ('PDF', 'DESIGN'):
        return _BINARY_SYSTEM
    return _DEFAULT_SYSTEM


def _detect_languages(student_content: str) -> str:
    """Extract unique file extensions from a flattened repo bundle marker lines."""
    if '===== FILE:' not in student_content:
        return ''
    exts = set(re.findall(r'===== FILE:[^\n]*\.(\w+)', student_content))
    if not exts:
        return ''
    return 'Detected file types in repository: ' + ', '.join(f'.{e}' for e in sorted(exts))


def build_evaluation_prompt(project_template: Any, student_content: str) -> tuple[str, str]:
    """
    Build ``(system_instruction, user_prompt)`` for project evaluation.

    Layers (system = role; user = context + student + output contract):

    1. System — submission-type-aware mentor role and global rules.
    2. Assignment context — template fields, instructions, rubric.
    3. Student content — extracted repository / documents / notes (passed in).
    4. Output instructions — exact JSON schema, raw JSON only.
    """
    submission_type = getattr(project_template, 'submission_type', '') or ''
    system = _system_for_type(submission_type, student_content)

    instruction = getattr(project_template, 'instruction', None)
    rubric = getattr(project_template, 'rubric', None)

    context_lines = [
        '## Layer 2 — Assignment context',
        f'**Title:** {project_template.title}',
        f'**Short description:** {getattr(project_template, "short_description", "") or ""}',
        f'**Business problem:** {getattr(project_template, "business_problem", "") or ""}',
        f'**Complexity:** {project_template.complexity}',
        f'**Submission type:** {submission_type}',
    ]
    if instruction:
        context_lines.extend(
            [
                f'**Instruction overview:** {instruction.overview or ""}',
                f'**Steps:** {json.dumps(instruction.steps or [], indent=2)}',
                f'**Deliverables:** {json.dumps(instruction.deliverables or [], indent=2)}',
                f'**Submission requirements:** {json.dumps(instruction.submission_requirements or [], indent=2)}',
                f'**Evaluation notes:** {instruction.evaluation_notes or ""}',
            ]
        )
    if rubric:
        context_lines.extend(
            [
                f'**Rubric passing score:** {rubric.passing_score}',
                f'**Rubric criteria:** {json.dumps(rubric.criteria or [], indent=2)}',
            ]
        )

    stripped_content = student_content.strip() or EMPTY_CONTENT_MARKER
    is_empty = stripped_content == EMPTY_CONTENT_MARKER

    student_lines = ['## Layer 3 — Student content']
    if is_empty:
        student_lines.append(
            'IMPORTANT: No student content was extractable from this submission. '
            'Set overall_score to 0. Set improvements to explain the submission was empty or unreadable.'
        )
    else:
        student_lines.append(
            'The following is the full student submission material (code bundle, documents, and/or typed notes).'
        )
        if submission_type.upper() == 'CODE':
            lang_hint = _detect_languages(stripped_content)
            if lang_hint:
                student_lines.append(lang_hint)
    student_lines.append('')
    student_lines.append(stripped_content)

    student_block = '\n'.join(student_lines)

    output_block = (
        '## Layer 4 — Output instructions\n'
        'Return exactly one JSON object with these keys only:\n'
        '{\n'
        '  "overall_score": <integer 0-100>,\n'
        '  "improvements": "<single string with concise feedback; use sentences separated by spaces or newlines>",\n'
        '  "extracted_tags": ["<short strings>", "..."]\n'
        '}\n'
        'Rules:\n'
        '- "overall_score" must be an integer.\n'
        '- "improvements" must be a single string (not an array).\n'
        '- "extracted_tags" must be an array of short skill/topic tags.\n'
        '- No extra keys. No markdown. No text before or after the JSON object.'
    )

    user = '\n\n'.join(['\n'.join(context_lines), student_block, output_block])
    return system, user
