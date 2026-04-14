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
    """Lightweight session row for listing."""

    class Meta:
        model = ChatSession
        fields = ('id', 'created_at')
        read_only_fields = fields


class ChatSendMessageSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=False, allow_null=True)
    content = serializers.CharField(trim_whitespace=True)

    def validate_content(self, value):
        text = (value or '').strip()
        if not text:
            raise serializers.ValidationError('Message cannot be empty.')
        return text
