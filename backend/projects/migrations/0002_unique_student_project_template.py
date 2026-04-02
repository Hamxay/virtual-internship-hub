from django.db import migrations, models
from django.db.models import Count


def dedupe_student_project_assignments(apps, schema_editor):
    Assignment = apps.get_model('projects', 'StudentProjectAssignment')
    Submission = apps.get_model('projects', 'ProjectSubmission')

    dup_groups = (
        Assignment.objects.values('student_id', 'project_template_id')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )

    priority = {
        'COMPLETED': 5,
        'IN_PROGRESS': 4,
        'SUBMITTED': 3,
        'NEEDS_REVISION': 2,
        'RECOMMENDED': 1,
    }

    for g in dup_groups:
        qs = list(
            Assignment.objects.filter(
                student_id=g['student_id'],
                project_template_id=g['project_template_id'],
            )
        )

        def sort_key(a):
            sub_n = Submission.objects.filter(assignment_id=a.pk).count()
            return (sub_n, priority.get(a.status, 0), a.assigned_at or a.pk)

        qs.sort(key=sort_key, reverse=True)
        keeper = qs[0]
        for other in qs[1:]:
            Submission.objects.filter(assignment_id=other.pk).update(assignment_id=keeper.pk)
            other.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(dedupe_student_project_assignments, noop_reverse),
        migrations.AddConstraint(
            model_name='studentprojectassignment',
            constraint=models.UniqueConstraint(
                fields=('student', 'project_template'),
                name='unique_student_project_template',
            ),
        ),
    ]
