from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator, IsStudent
from .models import ProjectSubmission, ProjectTemplate, StudentProjectAssignment
from .serializers import (
    AdminAssignProjectSerializer,
    ProjectSubmissionCreateSerializer,
    ProjectSubmissionSerializer,
    ProjectTemplateSerializer,
    StudentProgressSnapshotSerializer,
    StudentProjectAssignmentSerializer,
)
from .services.evaluation import evaluate_submission
from .services.recommendation import refresh_recommended_assignments, update_student_progress_snapshot


class AdminProjectTemplateListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = ProjectTemplateSerializer
    queryset = ProjectTemplate.objects.select_related('domain', 'instruction', 'rubric').all()


class AdminProjectTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = ProjectTemplateSerializer
    queryset = ProjectTemplate.objects.select_related('domain', 'instruction', 'rubric').all()


class AdminProjectAssignView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    def post(self, request):
        serializer = AdminAssignProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment, created = StudentProjectAssignment.objects.update_or_create(
            student=serializer.validated_data['student'],
            project_template=serializer.validated_data['project_template'],
            defaults={
                'status': 'IN_PROGRESS',
                'recommended_by': 'ADMIN',
                'recommendation_reason': serializer.validated_data.get(
                    'recommendation_reason', 'Assigned by administrator.'
                ),
                'due_date': serializer.validated_data.get('due_date'),
            },
        )
        return Response(
            StudentProjectAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class StudentRecommendedProjectsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        assignments = refresh_recommended_assignments(request.user)
        serializer = StudentProjectAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentAssignmentListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = StudentProjectAssignmentSerializer

    def get_queryset(self):
        return (
            StudentProjectAssignment.objects.filter(student=self.request.user)
            .select_related(
                'project_template__domain',
                'project_template__instruction',
                'project_template__rubric',
            )
            .prefetch_related('submissions__evaluations')
            .order_by('-assigned_at')
        )


class StudentProgressSnapshotView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        snapshot = update_student_progress_snapshot(request.user)
        return Response(StudentProgressSnapshotSerializer(snapshot).data, status=status.HTTP_200_OK)


class StudentAcceptProjectView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, pk):
        assignment = StudentProjectAssignment.objects.filter(student=request.user, pk=pk).select_related('project_template').first()
        if not assignment:
            return Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
        assignment.status = 'IN_PROGRESS'
        assignment.accepted_at = timezone.now()
        assignment.due_date = assignment.due_date or (timezone.now() + timedelta(days=7))
        assignment.save(update_fields=['status', 'accepted_at', 'due_date'])
        return Response(StudentProjectAssignmentSerializer(assignment).data, status=status.HTTP_200_OK)


class StudentSubmissionCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, pk):
        assignment = (
            StudentProjectAssignment.objects.filter(student=request.user, pk=pk)
            .select_related('project_template__rubric')
            .first()
        )
        if not assignment:
            return Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProjectSubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = assignment.submissions.count() + 1
        submission = ProjectSubmission.objects.create(
            assignment=assignment,
            version=version,
            **serializer.validated_data,
        )
        assignment.status = 'SUBMITTED'
        assignment.save(update_fields=['status'])
        evaluate_submission(submission)
        submission.refresh_from_db()
        return Response(ProjectSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


class StudentSubmissionFeedbackView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request, pk):
        submission = (
            ProjectSubmission.objects.filter(pk=pk, assignment__student=request.user)
            .prefetch_related('evaluations')
            .first()
        )
        if not submission:
            return Response({'detail': 'Submission not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectSubmissionSerializer(submission).data, status=status.HTTP_200_OK)


class AdminPendingSubmissionsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = ProjectSubmissionSerializer

    def get_queryset(self):
        return (
            ProjectSubmission.objects.filter(status__in=['SUBMITTED', 'FLAGGED'])
            .select_related('assignment__student', 'assignment__project_template__domain')
            .prefetch_related('evaluations')
            .order_by('-submitted_at')
        )


class AdminEvaluationSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    def get(self, request):
        assignments = StudentProjectAssignment.objects.all()
        submissions = ProjectSubmission.objects.all()
        status_counts = dict(assignments.values('status').annotate(count=Count('id')).values_list('status', 'count'))
        flagged = submissions.filter(status='FLAGGED').count()
        completed_avg = assignments.filter(status='COMPLETED').aggregate(avg=Avg('latest_evaluation_score'))
        return Response(
            {
                'template_count': ProjectTemplate.objects.count(),
                'assignment_count': assignments.count(),
                'submission_count': submissions.count(),
                'flagged_submissions': flagged,
                'status_breakdown': status_counts,
                'completed_projects': status_counts.get('COMPLETED', 0),
                'needs_revision': status_counts.get('NEEDS_REVISION', 0),
                'in_progress': status_counts.get('IN_PROGRESS', 0),
                'average_completed_score': round(completed_avg.get('avg') or 0, 2),
            },
            status=status.HTTP_200_OK,
        )
