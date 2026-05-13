from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_projectsubmission_uploaded_file'),
        ('chat', '0002_mentor_student_chat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mentorstudentconversation',
            name='assignment',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='mentor_chat_conversations',
                to='projects.studentprojectassignment',
            ),
        ),
    ]
