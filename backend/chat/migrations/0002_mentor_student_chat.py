from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_projectsubmission_uploaded_file'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MentorStudentConversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'assignment',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='mentor_chat_conversations',
                        to='projects.studentprojectassignment',
                    ),
                ),
                (
                    'mentor',
                    models.ForeignKey(
                        limit_choices_to={'role': 'MENTOR'},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='student_chat_conversations',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'student',
                    models.ForeignKey(
                        limit_choices_to={'role': 'STUDENT'},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='mentor_chat_conversations',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'mentor_student_conversations',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='MentorStudentMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                (
                    'conversation',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='messages',
                        to='chat.mentorstudentconversation',
                    ),
                ),
                (
                    'sender',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='mentor_student_messages',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'mentor_student_messages',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='mentorstudentconversation',
            constraint=models.UniqueConstraint(
                fields=('student', 'mentor', 'assignment'),
                name='unique_mentor_student_assignment_chat',
            ),
        ),
    ]
