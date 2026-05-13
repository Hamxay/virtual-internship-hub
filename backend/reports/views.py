"""Reports: audit CSV, admin analytics, mentor cohort, student progress."""
from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator, IsMentor, IsStudent

from .utils import (
    build_audit_csv_text,
    calculate_student_personal_progress,
    get_cohort_growth_analytics,
    get_mentor_cohort_summary,
    get_official_domain_names,
    get_platform_kpis,
    get_student_domain_scores,
)


class AdminAnalyticsView(APIView):
    """Admin KPIs and per-domain student score matrix."""

    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    def get(self, request):
        students = get_student_domain_scores()
        official_domains = get_official_domain_names()
        kpis = get_platform_kpis()
        cohort_growth_trends, domain_kpis = get_cohort_growth_analytics(max_steps=5)

        return Response(
            {
                "kpis": kpis,
                "students": students,
                "official_domains": official_domains,
                "cohort_growth_trends": cohort_growth_trends,
                "domain_kpis": domain_kpis,
            }
        )


class PlatformAuditExportView(APIView):
    """Download evaluation audit as CSV."""

    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    def get(self, request):
        body = build_audit_csv_text()
        resp = HttpResponse(body, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="platform_audit.csv"'
        return resp


class StudentPersonalProgressView(APIView):
    """Logged-in student's skill / progress summary."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        return Response(calculate_student_personal_progress(request.user))


class MentorCohortAnalyticsView(APIView):
    """Cohort summary scoped to the logged-in mentor."""

    permission_classes = [permissions.IsAuthenticated, IsMentor]

    def get(self, request):
        return Response(get_mentor_cohort_summary(request.user))
