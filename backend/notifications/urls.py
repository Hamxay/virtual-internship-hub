from django.urls import path

from .views import NotificationListView, NotificationMarkReadView, NotificationReadAllView

urlpatterns = [
    path('notifications/', NotificationListView.as_view()),
    path('notifications/<int:pk>/read/', NotificationMarkReadView.as_view()),
    path('notifications/read-all/', NotificationReadAllView.as_view()),
]
