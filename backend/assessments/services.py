"""
Assessment question selection, scoring, and domain recommendation (FR2).
- Composed test: up to 3 target domains, 10 questions per domain.
- Domain recommendation: rule-based (highest per-domain %); explanation + ranked top domains.
- Submit must use submission_token from GET composed (bound question set).
"""
from datetime import timedelta
import random
from typing import List, Tuple, Optional, Any, Dict, Union
from uuid import UUID

from django.utils import timezone

from accounts.models import Domain
from .models import AssessmentQuestion, ComposedAssessmentSession
from .ai_recommendation import DomainScores, recommend_rule_based_with_explanation

QUESTIONS_PER_DOMAIN = 10
COMPOSED_MAX_ATTEMPTS_PER_DAY = 2
MIN_TARGET_DOMAINS = 2
MAX_TARGET_DOMAINS_FOR_TEST = 3
PASSING_PERCENT = 70
COMPOSED_SESSION_MAX_AGE_HOURS = 2


def _get_questions_for_domain(domain_id: int) -> List[AssessmentQuestion]:
    return list(
        AssessmentQuestion.objects.filter(domain_id=domain_id)
        .order_by('order', 'id')
    )


def get_composed_questions(user) -> Tuple[List[dict], List[int]]:
    """
    Build the assessment for the student. Requires 2–3 target domains.
    Uses up to MAX_TARGET_DOMAINS_FOR_TEST domains, 10 questions per domain.
    Returns (list of question dicts for API, list of domain_ids in test).
    """
    profile = getattr(user, 'student_profile', None)
    questions_out: List[dict] = []
    domain_ids_in_test: List[int] = []

    if not profile or not profile.target_domains.exists():
        return questions_out, domain_ids_in_test

    target_ids = list(profile.target_domains.values_list('id', flat=True))
    if len(target_ids) < MIN_TARGET_DOMAINS:
        return questions_out, domain_ids_in_test

    domain_ids_to_use = target_ids[:MAX_TARGET_DOMAINS_FOR_TEST]
    for domain_id in domain_ids_to_use:
        qs = _get_questions_for_domain(domain_id)
        if len(qs) > QUESTIONS_PER_DOMAIN:
            qs = random.sample(qs, QUESTIONS_PER_DOMAIN)
        for q in qs:
            questions_out.append({
                'id': q.id,
                'text': q.text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'complexity': getattr(q, 'complexity', 'MEDIUM'),
                'order': q.order,
                'domain_id': domain_id,
            })
        if qs:
            domain_ids_in_test.append(domain_id)

    return questions_out, domain_ids_in_test


def create_composed_session(user, questions: List[dict]) -> ComposedAssessmentSession:
    """Replace any prior pending session; store issued question ids."""
    ComposedAssessmentSession.objects.filter(user=user).delete()
    qids = [q['id'] for q in questions]
    return ComposedAssessmentSession.objects.create(user=user, question_ids=qids)


def get_valid_composed_session(user, token: Union[UUID, str]) -> ComposedAssessmentSession:
    """Load session for user or raise ValueError (invalid / expired)."""
    try:
        if isinstance(token, str):
            token = UUID(str(token).strip())
    except (ValueError, TypeError):
        raise ValueError('Invalid submission token format.') from None

    session = ComposedAssessmentSession.objects.filter(user=user, token=token).first()
    if not session:
        raise ValueError(
            'Invalid submission token. Open the assessment again (GET student/assessments/composed/).'
        )
    age = timezone.now() - session.created_at
    if age > timedelta(hours=COMPOSED_SESSION_MAX_AGE_HOURS):
        session.delete()
        raise ValueError(
            'This assessment session expired. Start again from GET student/assessments/composed/.'
        )
    return session


def validate_answers_match_session(session: ComposedAssessmentSession, answer_question_ids: List[int]) -> None:
    issued = set(session.question_ids)
    answered = set(answer_question_ids)
    if issued != answered:
        raise ValueError(
            'Answers must cover exactly the questions issued for this assessment '
            '(same set of question ids, no extras or missing).'
        )


def compute_composed_score_and_recommend(
    answers: List[Tuple[int, str]]
) -> Tuple[int, int, int, DomainScores, Optional[int], Dict[str, Any]]:
    """
    Composed test: score answers, then rule-based recommendation + meta.
    answers: [(question_id, selected_option), ...]
    Returns (score, total_points, correct_count, per_domain, recommended_domain_id, recommendation_meta).
    """
    q_ids = [a[0] for a in answers]
    questions = {
        q.id: q
        for q in AssessmentQuestion.objects.filter(id__in=q_ids)
    }
    per_domain: DomainScores = {}
    total_score = 0
    total_points = 0
    correct_count = 0

    for q_id, selected in answers:
        q = questions.get(q_id)
        if not q or not q.domain_id:
            continue
        domain_id = q.domain_id
        pts = q.points
        total_points += pts
        correct = (selected or '').strip().upper() == (q.correct_option or '').strip().upper()
        if correct:
            total_score += pts
            correct_count += 1
        if domain_id not in per_domain:
            per_domain[domain_id] = (0, 0)
        s, t = per_domain[domain_id]
        per_domain[domain_id] = (s + (pts if correct else 0), t + pts)

    domain_names = {
        d.id: d.name
        for d in Domain.objects.filter(id__in=list(per_domain.keys()))
    }
    recommendation_meta = recommend_rule_based_with_explanation(per_domain, domain_names)
    recommended_id = recommendation_meta.get('recommended_domain_id')

    return total_score, total_points, correct_count, per_domain, recommended_id, recommendation_meta
