"""
Load project templates from a JSON file (bulk import via management command).
This is the only management command for seeding templates; use JSON for all catalog content.

Usage:
  python manage.py load_project_templates_json --file projects/data/my_templates.json
  python manage.py load_project_templates_json --file path/to/file.json --dry-run

JSON format: a top-level array of objects. Each object matches ProjectTemplateSerializer input:
  - domain_id (int) OR domain_code (str, matches accounts.Domain.code case-insensitively)
  - title, short_description, business_problem, complexity, submission_type, estimated_hours,
    tags, prerequisite_skills, expected_keywords, active
  - instruction: { overview, steps, deliverables, submission_requirements, starter_resources, evaluation_notes }
  - rubric: { passing_score, criteria, allow_auto_accept, plagiarism_threshold, grammar_weight } (all optional)

Uses update_or_create(domain, title) so re-running the same file updates existing rows.
All rows are applied in one database transaction (all succeed or none).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Domain
from projects.models import EvaluationRubric, ProjectInstruction, ProjectTemplate
from projects.serializers import DEFAULT_RUBRIC_CRITERIA, ProjectTemplateSerializer


def _resolve_domain(entry: dict, index: int) -> Domain:
    domain_id = entry.get('domain_id')
    domain_code = entry.get('domain_code')
    if domain_id is not None:
        domain = Domain.objects.filter(pk=domain_id).first()
        if not domain:
            raise CommandError(f'Entry {index}: no Domain with domain_id={domain_id}.')
        return domain
    if domain_code is not None and str(domain_code).strip():
        code = str(domain_code).strip()
        domain = Domain.objects.filter(code__iexact=code).first()
        if not domain:
            raise CommandError(
                f'Entry {index}: no Domain with domain_code={code!r}. '
                'Use a real code from the domains table.'
            )
        return domain
    raise CommandError(f'Entry {index}: provide domain_id or domain_code.')


def _prepare_payload(entry: dict, domain: Domain) -> dict:
    payload = {k: v for k, v in entry.items() if k != 'domain_code'}
    payload['domain_id'] = domain.pk
    if not payload.get('short_description') and payload.get('title'):
        payload['short_description'] = str(payload['title'])[:300]
    return payload


def _apply_entry(validated: Dict[str, Any]) -> bool:
    """Create or update template + instruction + rubric. Returns True if template row was created."""
    data = copy.deepcopy(dict(validated))
    instruction_data = data.pop('instruction', None) or {}
    rubric_data = data.pop('rubric', None) or {}
    domain = data.pop('domain')
    title = data.pop('title')

    template, created = ProjectTemplate.objects.update_or_create(
        domain=domain,
        title=title,
        defaults=data,
    )
    ProjectInstruction.objects.update_or_create(
        project_template=template,
        defaults=instruction_data,
    )
    rubric_defaults = {'criteria': DEFAULT_RUBRIC_CRITERIA, **rubric_data}
    if not rubric_defaults.get('criteria'):
        rubric_defaults['criteria'] = DEFAULT_RUBRIC_CRITERIA
    EvaluationRubric.objects.update_or_create(
        project_template=template,
        defaults=rubric_defaults,
    )
    return created


def _validate_all(raw: list) -> Tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    validated_rows: List[Dict[str, Any]] = []

    if not isinstance(raw, list):
        return [], ['JSON root must be an array of template objects.']

    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            errors.append(f'Entry {index}: must be an object, got {type(entry).__name__}.')
            continue
        try:
            domain = _resolve_domain(entry, index)
        except CommandError as e:
            errors.append(str(e))
            continue
        payload = _prepare_payload(entry, domain)
        serializer = ProjectTemplateSerializer(data=payload)
        if not serializer.is_valid():
            title_hint = entry.get('title', '?')
            errors.append(f'Entry {index} ({title_hint}): {serializer.errors}')
            continue
        validated_rows.append(copy.deepcopy(dict(serializer.validated_data)))

    return validated_rows, errors


class Command(BaseCommand):
    help = 'Import project templates from a JSON file (array of template objects).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            '-f',
            dest='file',
            required=True,
            help='Path to JSON file (array of template definitions).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate JSON and serializer only; do not write to the database.',
        )

    def handle(self, *args, **options):
        path = Path(options['file']).expanduser()
        if not path.is_file():
            raise CommandError(f'File not found: {path}')

        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON: {e}') from e

        validated_rows, errors = _validate_all(raw)
        if errors:
            for msg in errors:
                self.stdout.write(self.style.ERROR(msg))
            raise CommandError(f'{len(errors)} validation error(s). Fix the JSON and try again.')

        dry_run = options['dry_run']
        if dry_run:
            for i, vd in enumerate(validated_rows):
                self.stdout.write(f'[dry-run] OK entry {i}: {vd.get("title")}')
            self.stdout.write(self.style.SUCCESS(f'Dry-run OK: {len(validated_rows)} entr(y/ies) validated.'))
            return

        created_n = 0
        updated_n = 0
        with transaction.atomic():
            for vd in validated_rows:
                if _apply_entry(vd):
                    created_n += 1
                else:
                    updated_n += 1

        self.stdout.write(
            self.style.SUCCESS(f'Done. Created {created_n}, updated {updated_n}.')
        )
