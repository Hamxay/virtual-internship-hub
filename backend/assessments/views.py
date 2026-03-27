from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count
from accounts.permissions import IsAdministrator, IsStudent
from accounts.models import Domain
from .models import AssessmentQuestion, StudentAssessmentAttempt
from .serializers import (
    AssessmentQuestionSerializer,
    SubmitAnswersSerializer,
    AttemptResultSerializer,
    ComposedAssessmentSerializer,
)
from django.utils import timezone

from .services import (
    get_composed_questions,
    compute_composed_score_and_recommend,
    create_composed_session,
    COMPOSED_MAX_ATTEMPTS_PER_DAY,
    PASSING_PERCENT,
)
from .pagination import DomainQuestionPagination


# --------------- Admin: questions per domain ---------------

class AdminDomainQuestionListCreateView(generics.ListCreateAPIView):
    """GET/POST admin/domains/<domain_id>/questions/ – List or add MCQs for a domain (admin only). 5 per page."""
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = AssessmentQuestionSerializer
    pagination_class = DomainQuestionPagination

    def get_queryset(self):
        return AssessmentQuestion.objects.filter(
            domain_id=self.kwargs['domain_id']
        ).order_by('order', 'id')

    def perform_create(self, serializer):
        serializer.save(domain_id=self.kwargs['domain_id'])


class AdminDomainQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE admin/domains/<domain_id>/questions/<pk>/ – One question (admin only)."""
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = AssessmentQuestionSerializer

    def get_queryset(self):
        return AssessmentQuestion.objects.filter(
            domain_id=self.kwargs['domain_id']
        )

    def perform_destroy(self, instance):
        domain_id = instance.domain_id
        instance.delete()
        # Renumber remaining questions in this domain to 0, 1, 2, ...
        for idx, q in enumerate(
            AssessmentQuestion.objects.filter(domain_id=domain_id).order_by('order', 'id')
        ):
            if q.order != idx:
                q.order = idx
                q.save(update_fields=['order'])


class AdminDomainQuestionCountsView(APIView):
    """GET admin/domains/question-counts/ – Question count per domain (admin only)."""
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    def get(self, request):
        counts = (
            AssessmentQuestion.objects.values('domain_id')
            .annotate(question_count=Count('id'))
            .order_by('domain_id')
        )
        return Response([{'domain_id': c['domain_id'], 'question_count': c['question_count']} for c in counts])


# --------------- Student: composed assessment only ---------------

def _attempts_today(user):
    """Count attempts submitted today (global per user, not per target domain)."""
    today = timezone.now().date()
    return StudentAssessmentAttempt.objects.filter(
        user=user, submitted_at__date=today
    ).count()


class StudentComposedAssessmentView(APIView):
    """GET student/assessments/composed/ – Get composed assessment. Requires 2–3 target domains; 2 attempts per day."""
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        profile = getattr(request.user, 'student_profile', None)
        target_count = profile.target_domains.count() if profile else 0
        if target_count < 2:
            return Response(
                {'error': 'Select 2 to 3 domains of interest in your profile first, then you can take the assessment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        attempt_count_today = _attempts_today(request.user)
        if attempt_count_today >= COMPOSED_MAX_ATTEMPTS_PER_DAY:
            return Response(
                {'error': f'You can take the assessment up to {COMPOSED_MAX_ATTEMPTS_PER_DAY} times per day. Try again tomorrow.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        questions, test_domain_ids = get_composed_questions(request.user)
        if not questions:
            return Response(
                {'error': 'No questions available for your selected domains. Admin must add questions per domain first.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        session = create_composed_session(request.user, questions)
        data = {
            'questions': questions,
            'test_domain_ids': test_domain_ids,
            'max_attempts': COMPOSED_MAX_ATTEMPTS_PER_DAY,
            'attempt_count': attempt_count_today,
        }
        serializer = ComposedAssessmentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.data)
        payload['submission_token'] = str(session.token)
        return Response(payload, status=status.HTTP_200_OK)


class StudentComposedSubmitView(APIView):
    """POST student/assessments/composed/submit/ – Submit composed test. Pass 70%%; rule-based domain + explanation."""
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request):
        attempt_count_today = _attempts_today(request.user)
        if attempt_count_today >= COMPOSED_MAX_ATTEMPTS_PER_DAY:
            return Response(
                {'error': f'You can take the assessment up to {COMPOSED_MAX_ATTEMPTS_PER_DAY} times per day. Try again tomorrow.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SubmitAnswersSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        session = serializer.validated_data.pop('_composed_session')
        answers_data = serializer.validated_data['answers']
        answers_tuples = [(a['question_id'], a['selected_option']) for a in answers_data]

        score, total_points, correct_count, _per_domain, recommended_domain_id, recommendation_meta = (
            compute_composed_score_and_recommend(answers_tuples)
        )
        percentage = round((score / total_points * 100), 1) if total_points else 0
        passed = percentage >= PASSING_PERCENT
        question_count = len(answers_data)

        attempt = StudentAssessmentAttempt.objects.create(
            user=request.user,
            score=score,
            total_points=total_points,
            answers=answers_data,
            recommendation_meta=recommendation_meta,
        )
        if passed and recommended_domain_id is not None:
            attempt.recommended_domains.set([recommended_domain_id])
            profile = getattr(request.user, 'student_profile', None)
            if profile:
                profile.target_domains.add(recommended_domain_id)
        q_ids = [a['question_id'] for a in answers_data]
        domain_ids = list(
            AssessmentQuestion.objects.filter(id__in=q_ids)
            .values_list('domain_id', flat=True)
            .distinct()
        )
        if domain_ids:
            attempt.test_domains.set(domain_ids)

        session.delete()

        result = AttemptResultSerializer(attempt)
        data = result.data
        data['percentage'] = percentage
        data['passed'] = passed
        data['question_count'] = question_count
        data['correct_count'] = correct_count
        if not passed:
            data['message'] = 'Score below 70%%. Take the test again. You have 2 attempts per day.'
        return Response(data, status=status.HTTP_201_CREATED)


class StudentComposedSubmitMLView(StudentComposedSubmitView):
    """POST student/assessments/composed/submit-ml/ – Same as submit/. Kept for backward-compatible URL."""
    pass


class StudentAttemptListView(generics.ListAPIView):
    """GET student/attempts/ – List current user's assessment attempts."""
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = AttemptResultSerializer

    def get_queryset(self):
        return StudentAssessmentAttempt.objects.filter(
            user=self.request.user
        ).prefetch_related('recommended_domains', 'test_domains').order_by('-submitted_at')
