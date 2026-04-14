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
