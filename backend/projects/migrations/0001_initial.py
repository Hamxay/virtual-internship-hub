from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0002_pendingregistration_user_is_email_verified'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, max_length=240, unique=True)),
                ('short_description', models.CharField(max_length=300)),
                ('business_problem', models.TextField(blank=True)),
                ('complexity', models.CharField(choices=[('BEGINNER', 'Beginner'), ('INTERMEDIATE', 'Intermediate'), ('ADVANCED', 'Advanced')], default='BEGINNER', max_length=20)),
                ('submission_type', models.CharField(choices=[('CODE', 'Code'), ('DOCUMENT', 'Document'), ('DESIGN', 'Design')], default='CODE', max_length=20)),
                ('estimated_hours', models.PositiveIntegerField(default=8)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('prerequisite_skills', models.JSONField(blank=True, default=list)),
                ('expected_keywords', models.JSONField(blank=True, default=list)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('domain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_templates', to='accounts.domain')),
            ],
            options={
                'db_table': 'project_templates',
                'ordering': ['domain__name', 'complexity', 'title'],
            },
        ),
        migrations.CreateModel(
            name='ProjectInstruction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('overview', models.TextField(blank=True)),
                ('steps', models.JSONField(blank=True, default=list)),
                ('deliverables', models.JSONField(blank=True, default=list)),
                ('submission_requirements', models.JSONField(blank=True, default=list)),
                ('starter_resources', models.JSONField(blank=True, default=list)),
                ('evaluation_notes', models.TextField(blank=True)),
                ('project_template', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='instruction', to='projects.projecttemplate')),
            ],
            options={'db_table': 'project_instructions'},
        ),
        migrations.CreateModel(
            name='EvaluationRubric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('passing_score', models.PositiveIntegerField(default=70)),
                ('criteria', models.JSONField(blank=True, default=list)),
                ('allow_auto_accept', models.BooleanField(default=True)),
                ('plagiarism_threshold', models.FloatField(default=75.0)),
                ('grammar_weight', models.FloatField(default=15.0)),
                ('project_template', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='rubric', to='projects.projecttemplate')),
            ],
            options={'db_table': 'evaluation_rubrics'},
        ),
        migrations.CreateModel(
            name='StudentProjectAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('RECOMMENDED', 'Recommended'), ('IN_PROGRESS', 'In Progress'), ('SUBMITTED', 'Submitted'), ('NEEDS_REVISION', 'Needs Revision'), ('COMPLETED', 'Completed')], default='RECOMMENDED', max_length=20)),
                ('recommended_by', models.CharField(default='AI', max_length=50)),
                ('recommendation_score', models.FloatField(default=0.0)),
                ('recommendation_reason', models.TextField(blank=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('attempt_number', models.PositiveIntegerField(default=1)),
                ('latest_evaluation_score', models.FloatField(blank=True, null=True)),
                ('latest_feedback_summary', models.TextField(blank=True)),
                ('project_template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='projects.projecttemplate')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'student_project_assignments',
                'ordering': ['-assigned_at'],
            },
        ),
        migrations.CreateModel(
            name='StudentProgressSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed_projects', models.PositiveIntegerField(default=0)),
                ('average_score', models.FloatField(default=0.0)),
                ('current_complexity_band', models.CharField(choices=[('BEGINNER', 'Beginner'), ('INTERMEDIATE', 'Intermediate'), ('ADVANCED', 'Advanced')], default='BEGINNER', max_length=20)),
                ('last_recommended_at', models.DateTimeField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('strongest_domain', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='accounts.domain')),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='project_progress_snapshot', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'student_progress_snapshots'},
        ),
        migrations.CreateModel(
            name='ProjectSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1)),
                ('repository_url', models.URLField(blank=True)),
                ('artifact_url', models.URLField(blank=True)),
                ('submission_text', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('submitted_files', models.JSONField(blank=True, default=list)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('SUBMITTED', 'Submitted'), ('EVALUATED', 'Evaluated'), ('FLAGGED', 'Flagged')], default='SUBMITTED', max_length=20)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='projects.studentprojectassignment')),
            ],
            options={
                'db_table': 'project_submissions',
                'ordering': ['-submitted_at'],
            },
        ),
        migrations.CreateModel(
            name='SubmissionEvaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_name', models.CharField(default='local_hybrid_v1', max_length=120)),
                ('overall_score', models.FloatField(default=0.0)),
                ('correctness_score', models.FloatField(default=0.0)),
                ('originality_score', models.FloatField(default=0.0)),
                ('grammar_score', models.FloatField(default=0.0)),
                ('design_quality_score', models.FloatField(default=0.0)),
                ('rubric_scores', models.JSONField(blank=True, default=dict)),
                ('strengths', models.JSONField(blank=True, default=list)),
                ('improvements', models.JSONField(blank=True, default=list)),
                ('flags', models.JSONField(blank=True, default=list)),
                ('decision', models.CharField(choices=[('ACCEPTED', 'Accepted'), ('REVISE_AND_RESUBMIT', 'Revise And Resubmit'), ('NEEDS_MENTOR_REVIEW', 'Needs Mentor Review')], default='REVISE_AND_RESUBMIT', max_length=30)),
                ('feedback_summary', models.TextField(blank=True)),
                ('evaluation_payload', models.JSONField(blank=True, default=dict)),
                ('reviewed_at', models.DateTimeField(auto_now_add=True)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='projects.projectsubmission')),
            ],
            options={
                'db_table': 'submission_evaluations',
                'ordering': ['-reviewed_at'],
            },
        ),
    ]
