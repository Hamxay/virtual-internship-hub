from django.urls import path
from .views import (
    AdminDomainQuestionListCreateView,
    AdminDomainQuestionDetailView,
    AdminDomainQuestionCountsView,
    StudentComposedAssessmentView,
    StudentComposedSubmitView,
    StudentAttemptListView,
)

urlpatterns = [
    path('admin/domains/question-counts/', AdminDomainQuestionCountsView.as_view(), name='domain-question-counts'),
    path('admin/domains/<int:domain_id>/questions/', AdminDomainQuestionListCreateView.as_view(), name='domain-questions'),
    path('admin/domains/<int:domain_id>/questions/<int:pk>/', AdminDomainQuestionDetailView.as_view(), name='domain-question-detail'),
    path('student/assessments/composed/', StudentComposedAssessmentView.as_view(), name='student-assessment-composed'),
    path('student/assessments/composed/submit/', StudentComposedSubmitView.as_view(), name='student-assessment-composed-submit'),
    path('student/attempts/', StudentAttemptListView.as_view(), name='student-attempt-list'),
]
