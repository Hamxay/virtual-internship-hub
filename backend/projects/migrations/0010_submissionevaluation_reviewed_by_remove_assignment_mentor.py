from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_assignment_mentor_to_evaluation_reviewed_by(apps, schema_editor):
    """Preserve cohort attribution when dropping StudentProjectAssignment.mentor."""
    StudentProjectAssignment = apps.get_model('projects', 'StudentProjectAssignment')
    ProjectSubmission = apps.get_model('projects', 'ProjectSubmission')
    SubmissionEvaluation = apps.get_model('projects', 'SubmissionEvaluation')

    for asn in StudentProjectAssignment.objects.exclude(mentor_id=None).iterator():
        mentor_id = asn.mentor_id
        for sub in ProjectSubmission.objects.filter(assignment_id=asn.pk):
            ev = (
                SubmissionEvaluation.objects.filter(
                    submission_id=sub.pk,
                    is_human_reviewed=True,
                )
                .order_by('-reviewed_at', '-id')
                .first()
            )
            if ev and getattr(ev, 'reviewed_by_id', None) is None:
                ev.reviewed_by_id = mentor_id
                ev.save(update_fields=['reviewed_by'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0009_studentprojectassignment_mentor'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionevaluation',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Mentor who performed the human review (FCFS in domain; set on review).',
                limit_choices_to={'role': 'MENTOR'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='submission_evaluations_reviewed',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            copy_assignment_mentor_to_evaluation_reviewed_by,
            noop_reverse,
        ),
        migrations.RemoveField(
            model_name='studentprojectassignment',
            name='mentor',
        ),
    ]
