from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0008_fr5_mentor_review_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprojectassignment',
            name='mentor',
            field=models.ForeignKey(
                blank=True,
                help_text='Mentor associated with this assignment (set when a mentor reviews).',
                limit_choices_to={'role': 'MENTOR'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mentored_assignments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
