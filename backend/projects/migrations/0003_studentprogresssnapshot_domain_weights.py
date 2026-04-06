from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_unique_student_project_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprogresssnapshot',
            name='domain_weights',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='FR2 weighted domain profile for recommendations (domain id str -> percent).',
            ),
        ),
    ]
