from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile, User
from projects.models import ProjectSubmission

from .serializers import PublicProjectShowcaseSerializer, PublicStudentProfileSerializer


class PublicPortfolioView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, username):
        user = get_object_or_404(
            User.objects.select_related('student_profile').prefetch_related(
                'student_profile__target_domains',
            ),
            username=username,
        )
        get_object_or_404(StudentProfile, user=user)

        # ProjectSubmission has no COMPLETED status; assignment completion is tracked on
        # StudentProjectAssignment (see projects.models.ASSIGNMENT_STATUS_CHOICES).
        submissions = (
            ProjectSubmission.objects.filter(
                assignment__student__username=username,
                assignment__status='COMPLETED',
                evaluations__is_human_reviewed=True,
            )
            .select_related('assignment__project_template')
            .prefetch_related('evaluations')
            .order_by('-evaluations__overall_score')
            .distinct()[:4]
        )

        profile_data = PublicStudentProfileSerializer(user).data
        projects_data = PublicProjectShowcaseSerializer(submissions, many=True).data
        return Response({'profile': profile_data, 'top_projects': projects_data})
