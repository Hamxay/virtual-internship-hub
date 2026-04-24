from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsMentor
from projects.models import ProjectSubmission, SubmissionEvaluation
from projects.services.recommendation import update_student_progress_snapshot

from .serializers import MentorQueueSubmissionSerializer, MentorReviewActionSerializer


class MentorQueueView(APIView):
    """
    FR5 — Submissions needing mentor attention in the mentor's expertise domain.
    """

    permission_classes = [permissions.IsAuthenticated, IsMentor]

    def get(self, request):
        profile = getattr(request.user, 'mentor_profile', None)
        domain = getattr(profile, 'expertise_domain', None) if profile else None
        if not domain:
            return Response(
                {'detail': 'Set your expertise domain on your mentor profile to see the queue.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            ProjectSubmission.objects.filter(assignment__project_template__domain=domain)
            .filter(
                Q(status='FLAGGED')
                | Q(
                    evaluations__decision='NEEDS_MENTOR_REVIEW',
                    evaluations__is_human_reviewed=False,
                )
            )
            .select_related(
                'assignment',
                'assignment__student',
                'assignment__project_template',
                'assignment__project_template__domain',
            )
            .prefetch_related('evaluations')
            .distinct()
            .order_by('-submitted_at', '-id')
        )

        return Response(MentorQueueSubmissionSerializer(qs, many=True).data)


class MentorReviewActionView(APIView):
    """
    FR5 — Record mentor feedback and resolve assignment (approve → completed, else needs revision).
    Accepts POST or PATCH with the same JSON body.
    """

    permission_classes = [permissions.IsAuthenticated, IsMentor]

    def post(self, request):
        return self._review(request)

    def patch(self, request):
        return self._review(request)

    def _review(self, request):
        serializer = MentorReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission_id = serializer.validated_data['submission_id']
        mentor_feedback = serializer.validated_data.get('mentor_feedback') or ''
        approved = serializer.validated_data['approved']

        profile = getattr(request.user, 'mentor_profile', None)
        domain = getattr(profile, 'expertise_domain', None) if profile else None
        if not domain:
            return Response(
                {'detail': 'Mentor profile must have an expertise domain.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission = (
            ProjectSubmission.objects.filter(pk=submission_id)
            .select_related('assignment', 'assignment__project_template', 'assignment__student')
            .first()
        )
        if not submission:
            return Response({'detail': 'Submission not found.'}, status=status.HTTP_404_NOT_FOUND)

        if submission.assignment.project_template.domain_id != domain.id:
            return Response({'detail': 'Not allowed for this submission.'}, status=status.HTTP_403_FORBIDDEN)

        evaluation = (
            SubmissionEvaluation.objects.filter(submission=submission)
            .order_by('-reviewed_at', '-id')
            .first()
        )
        if not evaluation:
            return Response(
                {'detail': 'No evaluation record exists for this submission.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = submission.assignment

        with transaction.atomic():
            evaluation.mentor_feedback = mentor_feedback
            evaluation.is_human_reviewed = True
            evaluation.reviewed_by = request.user
            evaluation.save(
                update_fields=['mentor_feedback', 'is_human_reviewed', 'reviewed_by']
            )

            if approved:
                assignment.status = 'COMPLETED'
                assignment.completed_at = timezone.now()
                assignment.save(update_fields=['status', 'completed_at'])
            else:
                assignment.status = 'NEEDS_REVISION'
                assignment.completed_at = None
                assignment.save(update_fields=['status', 'completed_at'])

            # Clear FLAGGED so the submission no longer matches the mentor queue filter.
            if submission.status == 'FLAGGED':
                submission.status = 'EVALUATED'
                submission.save(update_fields=['status'])

        update_student_progress_snapshot(assignment.student)

        return Response(
            {
                'submission_id': submission.id,
                'assignment_status': assignment.status,
                'evaluation_id': evaluation.id,
                'is_human_reviewed': evaluation.is_human_reviewed,
            },
            status=status.HTTP_200_OK,
        )
