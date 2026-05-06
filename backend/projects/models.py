import uuid
from collections import Counter

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


PROJECT_COMPLEXITY_CHOICES = [
    ('BEGINNER', 'Beginner'),
    ('INTERMEDIATE', 'Intermediate'),
    ('ADVANCED', 'Advanced'),
]

SUBMISSION_TYPE_CHOICES = [
    ('CODE', 'Code (repo / implementation)'),
    ('DOCUMENT', 'Document (general written deliverable)'),
    ('DESIGN', 'Design (visual / UX / creative)'),
    ('PDF', 'PDF file'),
    ('WORD', 'Word / DOCX'),
    ('SPREADSHEET', 'Spreadsheet (e.g. Excel, Sheets)'),
]

ASSIGNMENT_STATUS_CHOICES = [
    ('RECOMMENDED', 'Recommended'),
    ('IN_PROGRESS', 'In Progress'),
    ('SUBMITTED', 'Submitted'),
    ('NEEDS_REVISION', 'Needs Revision'),
    ('PENDING_MENTOR_REVIEW', 'Pending Mentor Review'),
    ('COMPLETED', 'Completed'),
]

SUBMISSION_STATUS_CHOICES = [
    ('SUBMITTED', 'Submitted'),
    ('EVALUATED', 'Evaluated'),
    ('FLAGGED', 'Flagged'),
]

# Submission types that require an uploaded artifact (not a code repository URL).
FILE_SUBMISSION_TYPES = frozenset(
    {'DOCUMENT', 'DESIGN', 'PDF', 'WORD', 'SPREADSHEET'},
)

EVALUATION_DECISION_CHOICES = [
    ('ACCEPTED', 'Accepted'),
    ('REVISE_AND_RESUBMIT', 'Revise And Resubmit'),
    ('NEEDS_MENTOR_REVIEW', 'Needs Mentor Review'),
]

# FR3 separated feeds: how the row was produced (nullable for legacy / admin rows).
RECOMMENDATION_SOURCE_CHOICES = [
    ('COLD_START', 'Cold start'),
    ('CONTENT_BASED', 'Content based'),
    ('COLLABORATIVE', 'Collaborative'),
]


class ProjectTemplate(models.Model):
    domain = models.ForeignKey(
        'accounts.Domain',
        on_delete=models.CASCADE,
        related_name='project_templates',
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    short_description = models.CharField(max_length=300)
    business_problem = models.TextField(blank=True)
    complexity = models.CharField(
        max_length=20,
        choices=PROJECT_COMPLEXITY_CHOICES,
        default='BEGINNER',
    )
    submission_type = models.CharField(
        max_length=20,
        choices=SUBMISSION_TYPE_CHOICES,
        default='CODE',
    )
    estimated_hours = models.PositiveIntegerField(default=8)
    tags = models.JSONField(default=list, blank=True)
    prerequisite_skills = models.JSONField(default=list, blank=True)
    expected_keywords = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_templates'
        ordering = ['domain__name', 'complexity', 'title']

    def __str__(self):
        return f'{self.domain.name} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f'{self.domain.code}-{self.title}')[:220] or str(uuid.uuid4())
            slug = base_slug
            suffix = 2
            while ProjectTemplate.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base_slug[:230]}-{suffix}'
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ProjectInstruction(models.Model):
    project_template = models.OneToOneField(
        ProjectTemplate,
        on_delete=models.CASCADE,
        related_name='instruction',
    )
    overview = models.TextField(blank=True)
    steps = models.JSONField(default=list, blank=True)
    deliverables = models.JSONField(default=list, blank=True)
    submission_requirements = models.JSONField(default=list, blank=True)
    starter_resources = models.JSONField(default=list, blank=True)
    evaluation_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'project_instructions'

    def __str__(self):
        return f'Instructions for {self.project_template.title}'


class EvaluationRubric(models.Model):
    project_template = models.OneToOneField(
        ProjectTemplate,
        on_delete=models.CASCADE,
        related_name='rubric',
    )
    passing_score = models.PositiveIntegerField(default=70)
    criteria = models.JSONField(default=list, blank=True)
    allow_auto_accept = models.BooleanField(default=True)
    plagiarism_threshold = models.FloatField(default=75.0)
    grammar_weight = models.FloatField(default=15.0)

    class Meta:
        db_table = 'evaluation_rubrics'

    def __str__(self):
        return f'Rubric for {self.project_template.title}'


class StudentProjectAssignment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_assignments',
    )
    project_template = models.ForeignKey(
        ProjectTemplate,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    status = models.CharField(
        max_length=30,
        choices=ASSIGNMENT_STATUS_CHOICES,
        default='RECOMMENDED',
    )
    recommended_by = models.CharField(max_length=50, default='AI')
    recommendation_score = models.FloatField(default=0.0)
    recommendation_reason = models.TextField(blank=True)
    recommendation_source = models.CharField(
        max_length=20,
        choices=RECOMMENDATION_SOURCE_CHOICES,
        null=True,
        blank=True,
        help_text='FR3 feed: cold start, tag/content similarity, or collaborative filtering.',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    attempt_number = models.PositiveIntegerField(default=1)
    latest_evaluation_score = models.FloatField(null=True, blank=True)
    latest_feedback_summary = models.TextField(blank=True)

    class Meta:
        db_table = 'student_project_assignments'
        ordering = ['-assigned_at']
        constraints = [
            models.UniqueConstraint(
                fields=('student', 'project_template'),
                name='unique_student_project_template',
            ),
        ]

    def __str__(self):
        return f'{self.student_id} - {self.project_template.title}'

    @property
    def latest_submission(self):
        return self.submissions.order_by('-submitted_at', '-id').first()


class ProjectSubmission(models.Model):
    assignment = models.ForeignKey(
        StudentProjectAssignment,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    version = models.PositiveIntegerField(default=1)
    uploaded_file = models.FileField(
        upload_to='submissions/%Y/%m/',
        null=True,
        blank=True,
        help_text='Required for all submission types; CODE must upload a ZIP file.',
    )
    submission_text = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    submitted_files = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SUBMISSION_STATUS_CHOICES,
        default='SUBMITTED',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_submissions'
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Submission {self.assignment_id} v{self.version}'

    def clean(self):
        super().clean()
        if not self.assignment_id:
            return
        template = self.assignment.project_template
        submission_type = template.submission_type
        has_upload = bool(self.uploaded_file and getattr(self.uploaded_file, 'name', None))

        if not has_upload:
            if submission_type == 'CODE':
                raise ValidationError({'uploaded_file': 'Code submissions require a ZIP upload.'})
            raise ValidationError({'uploaded_file': 'This project type requires an uploaded file.'})


class SubmissionEvaluation(models.Model):
    submission = models.ForeignKey(
        ProjectSubmission,
        on_delete=models.CASCADE,
        related_name='evaluations',
    )
    model_name = models.CharField(max_length=120, default='local_hybrid_v1')
    overall_score = models.FloatField(default=0.0)
    correctness_score = models.FloatField(default=0.0)
    originality_score = models.FloatField(default=0.0)
    grammar_score = models.FloatField(default=0.0)
    design_quality_score = models.FloatField(default=0.0)
    rubric_scores = models.JSONField(default=dict, blank=True)
    strengths = models.JSONField(default=list, blank=True)
    improvements = models.JSONField(default=list, blank=True)
    flags = models.JSONField(default=list, blank=True)
    decision = models.CharField(
        max_length=30,
        choices=EVALUATION_DECISION_CHOICES,
        default='REVISE_AND_RESUBMIT',
    )
    feedback_summary = models.TextField(blank=True)
    evaluation_payload = models.JSONField(default=dict, blank=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)
    mentor_feedback = models.TextField(blank=True, null=True)
    is_human_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submission_evaluations_reviewed',
        limit_choices_to={'role': 'MENTOR'},
        help_text='Mentor who performed the human review (FCFS in domain; set on review).',
    )

    class Meta:
        db_table = 'submission_evaluations'
        ordering = ['-reviewed_at']

    def __str__(self):
        return f'Evaluation for submission {self.submission_id}'


class StudentProgressSnapshot(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_progress_snapshot',
    )
    strongest_domain = models.ForeignKey(
        'accounts.Domain',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
    )
    completed_projects = models.PositiveIntegerField(default=0)
    average_score = models.FloatField(default=0.0)
    current_complexity_band = models.CharField(
        max_length=20,
        choices=PROJECT_COMPLEXITY_CHOICES,
        default='BEGINNER',
    )
    last_recommended_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    # Normalized domain_id (str) -> weight_percent (0–100), sum ~100; from latest skill assessment
    domain_weights = models.JSONField(
        default=dict,
        blank=True,
        help_text='Weighted domain profile for recommendations (domain id str -> percent).',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student_progress_snapshots'

    def __str__(self):
        return f'Progress snapshot for {self.student_id}'

    def get_allowed_difficulties(self):
        """
        Allowed ``ProjectTemplate.complexity`` values for recommendations from this snapshot.

        Progression uses ``completed_projects`` and ``average_score`` on the snapshot.
        """
        completed_count = int(self.completed_projects or 0)
        average_score = float(self.average_score or 0.0)

        if completed_count <= 2:
            return ['BEGINNER']
        if 3 <= completed_count <= 5 and average_score >= 75.0:
            return ['BEGINNER', 'INTERMEDIATE']
        if completed_count >= 6 and average_score >= 85.0:
            return ['BEGINNER', 'INTERMEDIATE', 'ADVANCED']
        return ['BEGINNER']

    @classmethod
    def build_metadata(cls, assignments):
        completed = [a for a in assignments if a.latest_evaluation_score is not None]
        by_complexity = Counter(a.project_template.complexity for a in completed)
        return {
            'completed_assignments': len(completed),
            'by_complexity': dict(by_complexity),
            'generated_at': timezone.now().isoformat(),
        }
