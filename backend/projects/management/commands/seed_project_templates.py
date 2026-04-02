from django.core.management.base import BaseCommand

from accounts.models import Domain
from projects.catalog import build_template_specs
from projects.models import EvaluationRubric, ProjectInstruction, ProjectTemplate


class Command(BaseCommand):
    help = 'Create starter project templates, instructions, and rubrics for every domain.'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for domain in Domain.objects.all().order_by('name'):
            specs = build_template_specs(domain)
            for spec in specs:
                instruction_data = spec.pop('instruction')
                rubric_data = spec.pop('rubric')
                template, created = ProjectTemplate.objects.update_or_create(
                    domain=domain,
                    title=spec['title'],
                    defaults=spec,
                )
                ProjectInstruction.objects.update_or_create(
                    project_template=template,
                    defaults=instruction_data,
                )
                EvaluationRubric.objects.update_or_create(
                    project_template=template,
                    defaults=rubric_data,
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed complete. Created {created_count} templates and updated {updated_count} templates.'
            )
        )
