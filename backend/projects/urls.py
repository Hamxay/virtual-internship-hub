from django.urls import path

from .views import (
    AdminEvaluationSummaryView,
    AdminPendingSubmissionsView,
    AdminProjectAssignView,
    AdminProjectTemplateDetailView,
    AdminProjectTemplateListCreateView,
    StudentAcceptProjectView,
    StudentAssignmentListView,
    StudentProgressSnapshotView,
    StudentRecommendedProjectsView,
    StudentSubmissionCreateView,
    StudentSubmissionFeedbackView,
)


urlpatterns = [
    path('admin/project-templates/', AdminProjectTemplateListCreateView.as_view(), name='admin-project-template-list-create'),
    path('admin/project-templates/<int:pk>/', AdminProjectTemplateDetailView.as_view(), name='admin-project-template-detail'),
    path('admin/projects/assign/', AdminProjectAssignView.as_view(), name='admin-project-assign'),
    path('admin/submissions/pending/', AdminPendingSubmissionsView.as_view(), name='admin-pending-submissions'),
    path('admin/evaluations/summary/', AdminEvaluationSummaryView.as_view(), name='admin-evaluation-summary'),
    path('student/projects/recommended/', StudentRecommendedProjectsView.as_view(), name='student-project-recommended'),
    path('student/assignments/', StudentAssignmentListView.as_view(), name='student-assignment-list'),
    path('student/assignments/progress/', StudentProgressSnapshotView.as_view(), name='student-progress-snapshot'),
    path('student/projects/<int:pk>/accept/', StudentAcceptProjectView.as_view(), name='student-project-accept'),
    path('student/assignments/<int:pk>/submissions/', StudentSubmissionCreateView.as_view(), name='student-submission-create'),
    path('student/submissions/<int:pk>/feedback/', StudentSubmissionFeedbackView.as_view(), name='student-submission-feedback'),
]
