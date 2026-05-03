"""
Reports API: FR8 audit export, FR9 admin analytics, mentor cohort, student progress.
"""
from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator, IsMentor, IsStudent

from .utils import (
    build_audit_csv_text,
    calculate_student_personal_progress,
    get_mentor_cohort_summary,
    get_official_domain_names,
    get_platform_kpis,
    get_student_domain_scores,
)


class AdminAnalyticsView(APIView):
    """GET admin/reports/analytics/ — KPIs and domain-centric student score matrix."""

    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    def get(self, request):
        students = get_student_domain_scores()
        official_domains = get_official_domain_names()
        kpis = get_platform_kpis()

        return Response(
            {
                "kpis": kpis,
                "students": students,
                "official_domains": official_domains,
            }
        )


class PlatformAuditExportView(APIView):
    """GET admin/reports/export/ — FR8 audit as CSV."""

    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    def get(self, request):
        body = build_audit_csv_text()
        resp = HttpResponse(body, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="platform_audit.csv"'
        return resp


class StudentPersonalProgressView(APIView):
    """GET reports/student/me/ — FR9 skill delta for the logged-in student."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        return Response(calculate_student_personal_progress(request.user))


class MentorCohortAnalyticsView(APIView):
    """GET reports/mentor/cohort/ — mentor-scoped cohort summary."""

    permission_classes = [permissions.IsAuthenticated, IsMentor]

    def get(self, request):
        return Response(get_mentor_cohort_summary(request.user))
