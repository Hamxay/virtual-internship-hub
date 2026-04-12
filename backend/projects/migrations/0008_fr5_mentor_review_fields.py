from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_projectsubmission_uploaded_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentprojectassignment',
            name='status',
            field=models.CharField(
                choices=[
                    ('RECOMMENDED', 'Recommended'),
                    ('IN_PROGRESS', 'In Progress'),
                    ('SUBMITTED', 'Submitted'),
                    ('NEEDS_REVISION', 'Needs Revision'),
                    ('PENDING_MENTOR_REVIEW', 'Pending Mentor Review'),
                    ('COMPLETED', 'Completed'),
                ],
                default='RECOMMENDED',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='submissionevaluation',
            name='is_human_reviewed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='submissionevaluation',
            name='mentor_feedback',
            field=models.TextField(blank=True, null=True),
        ),
    ]
