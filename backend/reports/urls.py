from django.urls import path

from .views import (
    AdminAnalyticsView,
    MentorCohortAnalyticsView,
    PlatformAuditExportView,
    StudentPersonalProgressView,
)

urlpatterns = [
    path('analytics/', AdminAnalyticsView.as_view()),
    path('export/', PlatformAuditExportView.as_view()),
    path('student/me/', StudentPersonalProgressView.as_view()),
    path('mentor/cohort/', MentorCohortAnalyticsView.as_view()),
]
