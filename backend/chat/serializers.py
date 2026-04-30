from rest_framework import serializers

from .models import ChatMessage, ChatSession


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
