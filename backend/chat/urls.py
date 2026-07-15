from django.urls import path

from .views import (
    ChatSendMessageView,
    ChatSessionListView,
    ChatSessionMessagesListView,
    EligibleMentorListView,
    EligibleStudentListView,
    MentorStudentConversationStartView,
    MentorStudentConversationListView,
    MentorStudentMessageListCreateView,
)

urlpatterns = [
    path(
        'chat/mentor/eligible-mentors/',
        EligibleMentorListView.as_view(),
        name='mentor-student-eligible-mentor-list',
    ),
    path(
        'chat/mentor/eligible-students/',
        EligibleStudentListView.as_view(),
        name='mentor-student-eligible-student-list',
    ),
    path(
        'chat/mentor/conversations/start/',
        MentorStudentConversationStartView.as_view(),
        name='mentor-student-conversation-start',
    ),
    path(
        'chat/mentor/conversations/',
        MentorStudentConversationListView.as_view(),
        name='mentor-student-conversation-list',
    ),
    path(
        'chat/mentor/conversations/<int:conversation_id>/messages/',
        MentorStudentMessageListCreateView.as_view(),
        name='mentor-student-message-list-create',
    ),
    path('chat/message/', ChatSendMessageView.as_view(), name='chat-message'),
    path('chat/sessions/', ChatSessionListView.as_view(), name='chat-session-list'),
    path(
        'chat/sessions/<int:session_id>/messages/',
        ChatSessionMessagesListView.as_view(),
        name='chat-session-messages',
    ),
]
