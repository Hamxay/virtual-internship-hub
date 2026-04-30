import csv

from django.http import StreamingHttpResponse
from django.db.models import Prefetch
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdministrator
from projects.models import ProjectSubmission, ProjectTemplate, SubmissionEvaluation

from .utils import (
    calculate_skill_improvement,
    calculate_student_personal_progress,
    get_mentor_cohort_summary,
    get_student_clusters,
)


class AdminAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdministrator]

    def get(self, request, *args, **kwargs):
        kpis = {
            'total_students': User.objects.filter(role='STUDENT').count(),
            'total_mentors': User.objects.filter(role='MENTOR').count(),
            'total_projects': ProjectTemplate.objects.count(),
        }
        payload = {
            'kpis': kpis,
            'clusters': get_student_clusters(),
            'progress': calculate_skill_improvement(),
        }
        return Response(payload)


class _CSVBuffer:
    """An object that implements just the write method of the file-like interface."""

    def write(self, value):
        return value


class PlatformAuditExportView(APIView):
    permission_classes = [IsAuthenticated, IsAdministrator]

    def get(self, request, *args, **kwargs):
        qs = (
            ProjectSubmission.objects.filter(assignment__status='COMPLETED')
            .select_related(
                'assignment__student',
                'assignment__project_template',
                'assignment__project_template__domain',
            )
            .prefetch_related(
                Prefetch(
                    'evaluations',
                    queryset=SubmissionEvaluation.objects.order_by('-reviewed_at'),
                )
            )
            .order_by('submitted_at', 'id')
        )

        def rows():
            buffer = _CSVBuffer()
            writer = csv.writer(buffer)
            yield writer.writerow(
                [
                    'Date',
                    'Student Username',
                    'Project Title',
                    'Domain',
                    'AI Score',
                    'Mentor Status',
                ]
            )
            for submission in qs.iterator(chunk_size=500):
                template = submission.assignment.project_template
                tags = template.tags or []
                if isinstance(tags, list) and tags:
                    domain_cell = ', '.join(str(t) for t in tags)
                else:
                    domain_cell = (
                        template.domain.name if template.domain_id else ''
                    )
                latest_ev = submission.evaluations.first()
                ai_score = ''
                if latest_ev is not None:
                    ai_score = latest_ev.overall_score
                yield writer.writerow(
                    [
                        submission.submitted_at.isoformat()
                        if submission.submitted_at
                        else '',
                        submission.assignment.student.username,
                        template.title,
                        domain_cell,
                        ai_score,
                        submission.assignment.status,
                    ]
                )

        response = StreamingHttpResponse(rows(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="platform_audit.csv"'
        return response


class StudentPersonalProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'STUDENT':
            return Response(
                {'detail': 'Only students can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(calculate_student_personal_progress(request.user))


class MentorCohortAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'MENTOR':
            return Response(
                {'detail': 'Only mentors can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(get_mentor_cohort_summary(request.user))
