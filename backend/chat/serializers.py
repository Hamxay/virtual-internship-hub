from rest_framework import serializers

from .models import (
    ChatMessage,
    ChatSession,
    MentorStudentConversation,
    MentorStudentMessage,
)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ('id', 'role', 'content', 'timestamp')
        read_only_fields = fields


class ChatSessionSerializer(serializers.ModelSerializer):
    """Session with nested messages (e.g. history endpoint)."""

    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = ('id', 'created_at', 'messages')
        read_only_fields = fields


class ChatSessionListSerializer(serializers.ModelSerializer):
    """Lightweight session row for listing — includes first-message preview."""

    preview = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = ('id', 'created_at', 'preview')
        read_only_fields = fields

    def get_preview(self, obj):
        first = obj.messages.filter(role='user').order_by('timestamp', 'id').first()
        if not first:
            return None
        text = first.content or ''
        return text[:60] + ('…' if len(text) > 60 else '')


class ChatSendMessageSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=False, allow_null=True)
    content = serializers.CharField(trim_whitespace=True)

    def validate_content(self, value):
        text = (value or '').strip()
        if not text:
            raise serializers.ValidationError('Message cannot be empty.')
        return text


class ChatSendMessageResponseSerializer(serializers.Serializer):
    """OpenAPI / drf-spectacular only — mirrors ChatSendMessageView success payload."""

    session_id = serializers.IntegerField()
    user_message = ChatMessageSerializer()
    assistant_message = ChatMessageSerializer()


class ServiceUnavailableSerializer(serializers.Serializer):
    """503 payload when OpenRouter is not configured or returns an error."""

    detail = serializers.CharField()


class MentorStudentMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    sender_role = serializers.CharField(source='sender.role', read_only=True)
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = MentorStudentMessage
        fields = (
            'id',
            'sender_id',
            'sender_role',
            'sender_username',
            'content',
            'created_at',
            'read_at',
        )
        read_only_fields = fields


class MentorStudentConversationSerializer(serializers.ModelSerializer):
    assignment_id = serializers.IntegerField(source='assignment.id', read_only=True)
    assignment_status = serializers.CharField(source='assignment.status', read_only=True)
    project_title = serializers.SerializerMethodField()
    domain_name = serializers.SerializerMethodField()
    mentor_domain_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    mentor_name = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = MentorStudentConversation
        fields = (
            'id',
            'assignment_id',
            'assignment_status',
            'project_title',
            'domain_name',
            'mentor_domain_name',
            'student_name',
            'mentor_name',
            'created_at',
            'updated_at',
            'last_message',
            'unread_count',
        )
        read_only_fields = fields

    def get_student_name(self, obj):
        return obj.student.username

    def get_mentor_name(self, obj):
        return obj.mentor.username

    def get_mentor_domain_name(self, obj):
        profile = getattr(obj.mentor, 'mentor_profile', None)
        domain = getattr(profile, 'expertise_domain', None) if profile else None
        return domain.name if domain else ''

    def get_project_title(self, obj):
        if obj.assignment_id and getattr(obj.assignment, 'project_template', None):
            return obj.assignment.project_template.title
        return 'General mentor chat'

    def get_domain_name(self, obj):
        if obj.assignment_id and getattr(obj.assignment, 'project_template', None):
            domain = getattr(obj.assignment.project_template, 'domain', None)
            if domain:
                return domain.name
        profile = getattr(obj.mentor, 'mentor_profile', None)
        domain = getattr(profile, 'expertise_domain', None) if profile else None
        return domain.name if domain else ''

    def get_last_message(self, obj):
        last = getattr(obj, '_prefetched_last_message', None)
        if last is None:
            last = obj.messages.order_by('-created_at', '-id').first()
        if not last:
            return None
        text = (last.content or '').strip()
        return text[:80] + ('...' if len(text) > 80 else '')

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(read_at__isnull=True).exclude(sender=request.user).count()


class MentorStudentConversationStartSerializer(serializers.Serializer):
    mentor_id = serializers.IntegerField()


class MentorStudentMessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(trim_whitespace=True)

    def validate_content(self, value):
        text = (value or '').strip()
        if not text:
            raise serializers.ValidationError('Message cannot be empty.')
        return text


class EligibleMentorSerializer(serializers.Serializer):
    mentor_id = serializers.IntegerField()
    username = serializers.CharField()
    expertise_domain_id = serializers.IntegerField(allow_null=True)
    expertise_domain_name = serializers.CharField(allow_blank=True)
