from django.urls import path

from .views import ChatSendMessageView, ChatSessionListView, ChatSessionMessagesListView

urlpatterns = [
    path('chat/message/', ChatSendMessageView.as_view(), name='chat-message'),
    path('chat/sessions/', ChatSessionListView.as_view(), name='chat-session-list'),
    path(
        'chat/sessions/<int:session_id>/messages/',
        ChatSessionMessagesListView.as_view(),
        name='chat-session-messages',
    ),
]
