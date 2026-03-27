"""
Skill assessment models (FR2). Domain and User live in accounts.
Questions are per-domain; no separate SkillAssessment container.
"""
import uuid

from django.conf import settings
from django.db import models


class AssessmentQuestion(models.Model):
    """MCQ question for a domain (admin adds; used in composed student assessment)."""
    CORRECT_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
    COMPLEXITY_CHOICES = [
        ('EASY', 'Easy'),
        ('MEDIUM', 'Medium'),
        ('HARD', 'Hard'),
    ]

    domain = models.ForeignKey(
        'accounts.Domain',
        on_delete=models.CASCADE,
        related_name='assessment_questions',
    )
    text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(max_length=1, choices=CORRECT_CHOICES)
    complexity = models.CharField(
        max_length=10,
        choices=COMPLEXITY_CHOICES,
        default='MEDIUM',
    )
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'assessment_questions'
        ordering = ['domain', 'order', 'id']

    def __str__(self):
        return f"Q{self.order} – {self.text[:50]}…"


class ComposedAssessmentSession(models.Model):
    """
    Binds a GET /composed/ question set to a later submit.
    Prevents submitting answers for questions that were not issued for this attempt.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='composed_assessment_sessions',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    question_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'composed_assessment_sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_id} – {self.token}"


class StudentAssessmentAttempt(models.Model):
    """One student's submission: score, test_domains, recommended_domains (FR2). Composed only."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assessment_attempts',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveIntegerField(default=0)
    total_points = models.PositiveIntegerField(default=0)
    test_domains = models.ManyToManyField(
        'accounts.Domain',
        related_name='+',
        blank=True,
        help_text='Domains this test was taken for.',
    )
    recommended_domains = models.ManyToManyField(
        'accounts.Domain',
        related_name='+',
        blank=True,
    )
    answers = models.JSONField(default=list, blank=True)
    recommendation_meta = models.JSONField(
        default=dict,
        blank=True,
        help_text='Rule-based ranked domains, explanation, method (FR2).',
    )

    class Meta:
        db_table = 'student_assessment_attempts'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.username} – {self.score}/{self.total_points}"
