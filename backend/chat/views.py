from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent

from .models import ChatMessage, ChatSession
from .serializers import (
    ChatMessageSerializer,
    ChatSendMessageSerializer,
    ChatSessionListSerializer,
)
from .utils import build_career_coach_prompt, run_career_coach_gemini


class ChatSessionListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ChatSessionListSerializer

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).order_by('-created_at')


class ChatSendMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        ser = ChatSendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        session_id = ser.validated_data.get('session_id')
        content = ser.validated_data['content']

        if session_id is None:
            session = ChatSession.objects.create(user=request.user)
        else:
            session = get_object_or_404(ChatSession, pk=session_id, user=request.user)

        user_message = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            content=content,
        )

        recent = list(
            session.messages.order_by('-timestamp', '-id').values_list('role', 'content')[:5]
        )
        recent.reverse()
        history = [(role, text) for role, text in recent]

        system_instruction = build_career_coach_prompt(request.user)
        try:
            reply_text = run_career_coach_gemini(system_instruction, history)
        except RuntimeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        assistant = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_MODEL,
            content=reply_text,
        )

        return Response(
            {
                'session_id': session.pk,
                'user_message': ChatMessageSerializer(user_message).data,
                'assistant_message': ChatMessageSerializer(assistant).data,
            },
            status=status.HTTP_200_OK,
        )


class ChatSessionMessagesListView(generics.ListAPIView):
    """GET flat list of messages for a session (chronological)."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ChatMessageSerializer
    pagination_class = None

    def get_queryset(self):
        session = get_object_or_404(
            ChatSession,
            pk=self.kwargs['session_id'],
            user=self.request.user,
        )
        return session.messages.order_by('timestamp', 'id')
