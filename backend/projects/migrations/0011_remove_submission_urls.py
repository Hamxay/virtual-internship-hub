from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0010_submissionevaluation_reviewed_by_remove_assignment_mentor'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='projectsubmission',
            name='artifact_url',
        ),
        migrations.RemoveField(
            model_name='projectsubmission',
            name='repository_url',
        ),
    ]

