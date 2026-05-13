from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f'ChatSession {self.pk} ({self.user_id})'


class ChatMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_MODEL = 'model'
    ROLE_CHOICES = [
        (ROLE_USER, 'User'),
        (ROLE_MODEL, 'Model'),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['timestamp', 'id']

    def __str__(self):
        return f'ChatMessage {self.pk} ({self.role})'


class MentorStudentConversation(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mentor_chat_conversations',
        limit_choices_to={'role': 'STUDENT'},
    )
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_chat_conversations',
        limit_choices_to={'role': 'MENTOR'},
    )
    assignment = models.ForeignKey(
        'projects.StudentProjectAssignment',
        on_delete=models.CASCADE,
        related_name='mentor_chat_conversations',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mentor_student_conversations'
        ordering = ['-updated_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=('student', 'mentor', 'assignment'),
                name='unique_mentor_student_assignment_chat',
            ),
        ]

    def __str__(self):
        return f'Conversation {self.pk} (student={self.student_id}, mentor={self.mentor_id})'


class MentorStudentMessage(models.Model):
    conversation = models.ForeignKey(
        MentorStudentConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mentor_student_messages',
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'mentor_student_messages'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'MentorStudentMessage {self.pk} (conversation={self.conversation_id})'
