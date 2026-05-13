from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from accounts.models import User

from .models import (
    ChatMessage,
    ChatSession,
    MentorStudentConversation,
    MentorStudentMessage,
)
from .serializers import (
    ChatMessageSerializer,
    ChatSendMessageResponseSerializer,
    ChatSendMessageSerializer,
    ChatSessionListSerializer,
    ServiceUnavailableSerializer,
    MentorStudentConversationSerializer,
    MentorStudentConversationStartSerializer,
    MentorStudentMessageCreateSerializer,
    MentorStudentMessageSerializer,
    EligibleMentorSerializer,
)
from .scope import OFF_SCOPE_COACH_REPLY, user_message_in_career_scope
from .utils import build_career_coach_prompt, run_career_coach


def _push_notification_ws(user_id: int, data: dict) -> None:
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {'type': 'send_notification', 'data': data},
    )


class ChatSessionListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ChatSessionListSerializer

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).order_by('-created_at')


class ChatSendMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(
        summary='Send career coach message',
        description=(
            'Student-only. Sends a user message; creates a new chat session if `session_id` '
            'is omitted. Uses OpenRouter (`OPENROUTER_API_KEY`, `OPENROUTER_CHAT_MODEL`). '
            'Obvious biography/trivia or code-help prompts without a career link may get a '
            'fixed refusal (no LLM call). Project AI evaluation also uses OpenRouter.'
        ),
        request=ChatSendMessageSerializer,
        responses={
            200: ChatSendMessageResponseSerializer,
            401: OpenApiResponse(description='Not authenticated'),
            403: OpenApiResponse(description='Not a student'),
            503: OpenApiResponse(
                response=ServiceUnavailableSerializer,
                description='LLM not configured, rate limited, or provider error',
            ),
        },
        tags=['chat'],
    )
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
        if not user_message_in_career_scope(content):
            reply_text = OFF_SCOPE_COACH_REPLY
        else:
            try:
                reply_text = run_career_coach(system_instruction, history)
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


def _eligible_mentors_for_student(user):
    profile = getattr(user, 'student_profile', None)
    if not profile:
        return User.objects.none()
    target_domain_ids = list(
        profile.target_domains.values_list('id', flat=True)
    )
    if not target_domain_ids:
        return User.objects.none()
    return User.objects.filter(
        role='MENTOR',
        mentor_profile__is_available=True,
        mentor_profile__expertise_domain_id__in=target_domain_ids,
    ).select_related('mentor_profile', 'mentor_profile__expertise_domain').order_by('username', 'id')


class EligibleMentorListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        mentors = _eligible_mentors_for_student(request.user)
        payload = [
            {
                'mentor_id': mentor.id,
                'username': mentor.username,
                'expertise_domain_id': getattr(mentor.mentor_profile, 'expertise_domain_id', None),
                'expertise_domain_name': (
                    mentor.mentor_profile.expertise_domain.name
                    if getattr(mentor.mentor_profile, 'expertise_domain', None)
                    else ''
                ),
            }
            for mentor in mentors
        ]
        return Response(EligibleMentorSerializer(payload, many=True).data, status=status.HTTP_200_OK)


class MentorStudentConversationStartView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        serializer = MentorStudentConversationStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mentor_id = serializer.validated_data['mentor_id']
        mentor = get_object_or_404(User.objects.select_related('mentor_profile', 'mentor_profile__expertise_domain'), pk=mentor_id, role='MENTOR')
        if not getattr(mentor, 'mentor_profile', None) or not mentor.mentor_profile.is_available:
            return Response({'detail': 'Selected mentor is not available.'}, status=status.HTTP_409_CONFLICT)

        profile = getattr(request.user, 'student_profile', None)
        target_domain_ids = set(profile.target_domains.values_list('id', flat=True)) if profile else set()
        if mentor.mentor_profile.expertise_domain_id not in target_domain_ids:
            return Response(
                {'detail': 'Selected mentor must match one of your target domains.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        conversation = (
            MentorStudentConversation.objects.filter(
                student=request.user,
                mentor=mentor,
                assignment__isnull=True,
            ).order_by('-updated_at', '-id').first()
        )
        if not conversation:
            conversation = MentorStudentConversation.objects.create(
                student=request.user,
                mentor=mentor,
                assignment=None,
            )

        payload = MentorStudentConversationSerializer(conversation, context={'request': request}).data
        return Response(payload, status=status.HTTP_200_OK)


class MentorStudentConversationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MentorStudentConversationSerializer
    pagination_class = None

    def get_queryset(self):
        qs = MentorStudentConversation.objects.select_related(
            'student',
            'mentor',
            'mentor__mentor_profile',
            'mentor__mentor_profile__expertise_domain',
            'assignment',
            'assignment__project_template',
            'assignment__project_template__domain',
        )
        user = self.request.user
        if user.is_student:
            return qs.filter(student=user).order_by('-updated_at', '-id')
        if user.is_mentor:
            return qs.filter(mentor=user).order_by('-updated_at', '-id')
        return qs.none()


class MentorStudentMessageListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_conversation(self, request, conversation_id):
        return get_object_or_404(
            MentorStudentConversation.objects.select_related('student', 'mentor'),
            Q(pk=conversation_id)
            & (Q(student=request.user) | Q(mentor=request.user)),
        )

    def get(self, request, conversation_id):
        conversation = self._get_conversation(request, conversation_id)
        qs = conversation.messages.select_related('sender').order_by('created_at', 'id')
        unread_ids = list(
            qs.filter(read_at__isnull=True).exclude(sender=request.user).values_list('id', flat=True)
        )
        if unread_ids:
            MentorStudentMessage.objects.filter(id__in=unread_ids).update(read_at=timezone.now())
        data = MentorStudentMessageSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, conversation_id):
        conversation = self._get_conversation(request, conversation_id)
        serializer = MentorStudentMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = MentorStudentMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            content=serializer.validated_data['content'],
        )
        conversation.save(update_fields=['updated_at'])

        recipient = (
            conversation.mentor
            if request.user.id == conversation.student_id
            else conversation.student
        )
        from notifications.models import Notification
        from notifications.serializers import NotificationSerializer

        dashboard_link = (
            '/mentor/dashboard?mentor_tab=chat'
            if recipient.role == 'MENTOR'
            else '/student/dashboard?student_tab=chat'
        )
        preview = serializer.validated_data['content'].strip()
        if len(preview) > 80:
            preview = f'{preview[:80]}...'
        notification = Notification.objects.create(
            recipient=recipient,
            message=f'New chat message from {request.user.username}: {preview}',
            link=dashboard_link,
        )
        payload = NotificationSerializer(notification).data
        transaction.on_commit(lambda: _push_notification_ws(recipient.id, payload))

        data = MentorStudentMessageSerializer(message).data
        return Response(data, status=status.HTTP_201_CREATED)
