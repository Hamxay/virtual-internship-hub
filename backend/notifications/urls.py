from django.urls import path

from .views import NotificationListView, NotificationMarkReadView, NotificationReadAllView

urlpatterns = [
    path('notifications/', NotificationListView.as_view()),
    # Literal path must come before <int:pk> so "read-all" is never captured as an id.
    path('notifications/read-all/', NotificationReadAllView.as_view()),
    path('notifications/<int:pk>/read/', NotificationMarkReadView.as_view()),
]
