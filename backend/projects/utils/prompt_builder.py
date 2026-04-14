"""
Strict 4-layer prompts for FR4 Gemini evaluation (language-agnostic).
"""
from __future__ import annotations

import json
from typing import Any


def build_evaluation_prompt(project_template: Any, student_content: str) -> tuple[str, str]:
    """
    Build ``(system_instruction, user_prompt)`` for Gemini.

    Layers (system = role; user = context + student + output contract):

    1. System — mentor role and global rules.
    2. Assignment context — template fields, instructions, rubric.
    3. Student content — extracted repository / documents / notes (passed in).
    4. Output instructions — exact JSON schema, raw JSON only.
    """
    system = (
        'You are a Senior Technical Mentor evaluating a student project submission.\n'
        'You must be fair, specific, and constructive. Base every judgment only on the '
        'assignment context and the student content provided in the user message.\n'
        'Respond with strictly valid raw JSON only — no markdown fences, no commentary.'
    )

    instruction = getattr(project_template, 'instruction', None)
    rubric = getattr(project_template, 'rubric', None)

    context_lines = [
        '## Layer 2 — Assignment context',
        f'**Title:** {project_template.title}',
        f'**Short description:** {getattr(project_template, "short_description", "") or ""}',
        f'**Business problem:** {getattr(project_template, "business_problem", "") or ""}',
        f'**Complexity:** {project_template.complexity}',
        f'**Submission type:** {project_template.submission_type}',
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

    student_block = (
        '## Layer 3 — Student content\n'
        'The following is the full student submission material (code bundle, documents, '
        'and/or typed notes). Treat binary uploads (if any) as attached files you already '
        'received alongside this text.\n\n'
        f'{student_content.strip() or "(no extractable student content)"}'
    )

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
