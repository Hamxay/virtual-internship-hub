"""
Composed assessment flow: pick questions, score MCQs, blend rule-based + ML domain recommendation.
"""
from datetime import timedelta
import random
from typing import List, Tuple, Optional, Any, Dict, Union
from uuid import UUID

from django.utils import timezone

from accounts.models import Domain
from projects.models import StudentProgressSnapshot
from projects.services.domain_profile import extract_domain_weights_from_recommendation_meta

from .models import AssessmentQuestion, ComposedAssessmentSession, StudentAssessmentAttempt
from .domain_recommendation import (
    DomainScores,
    build_ml_recommendation_meta,
    recommend_rule_based_with_explanation,
)

QUESTIONS_PER_DOMAIN = 10
COMPOSED_MAX_ATTEMPTS_PER_DAY = 2
MIN_TARGET_DOMAINS = 2
MAX_TARGET_DOMAINS_FOR_TEST = 3
PASSING_PERCENT = 70
COMPOSED_SESSION_MAX_AGE_HOURS = 2
# Must match StudentProfileSerializer / product rule (2–3 target domains max)
MAX_STUDENT_TARGET_DOMAINS = 3


def _get_questions_for_domain(domain_id: int) -> List[AssessmentQuestion]:
    return list(
        AssessmentQuestion.objects.filter(domain_id=domain_id)
        .order_by('order', 'id')
    )


def get_composed_questions(user) -> Tuple[List[dict], List[int]]:
    """
    Build the assessment for the student. Requires 2–3 target domains.
    Uses up to MAX_TARGET_DOMAINS_FOR_TEST domains (stable order by domain id), 10 questions per domain.
    Returns (list of question dicts for API, list of domain_ids in test).
    """
    profile = getattr(user, 'student_profile', None)
    questions_out: List[dict] = []
    domain_ids_in_test: List[int] = []

    if not profile or not profile.target_domains.exists():
        return questions_out, domain_ids_in_test

    target_ids = list(
        profile.target_domains.order_by('id').values_list('id', flat=True)
    )
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
    issued_list = session.question_ids
    if len(answer_question_ids) != len(issued_list):
        raise ValueError(
            'Each issued question must be answered exactly once (no duplicates or missing ids).'
        )
    issued = set(issued_list)
    answered = set(answer_question_ids)
    if issued != answered:
        raise ValueError(
            'Answers must cover exactly the questions issued for this assessment '
            '(same set of question ids, no extras or missing).'
        )


def add_recommended_domain_if_room(profile, domain_id: Optional[int]) -> bool:
    """
    Add recommended domain to student profile without exceeding MAX_STUDENT_TARGET_DOMAINS.
    Returns True if the domain is now in target_domains (added or already present).
    Returns False if profile is missing, domain_id is None, or profile is full and domain not yet selected.
    """
    if profile is None or domain_id is None:
        return False
    existing_ids = set(profile.target_domains.values_list('id', flat=True))
    if domain_id in existing_ids:
        return True
    if profile.target_domains.count() >= MAX_STUDENT_TARGET_DOMAINS:
        return False
    profile.target_domains.add(domain_id)
    return True


def _score_composed_answers(
    answers: List[Tuple[int, str]],
) -> Tuple[int, int, int, DomainScores]:
    """
    Shared scoring for composed MCQ answers (rule-based correctness only).
    Returns (total_score, total_points, correct_count, per_domain).
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

    return total_score, total_points, correct_count, per_domain


def compute_composed_score_and_recommend(
    answers: List[Tuple[int, str]]
) -> Tuple[int, int, int, DomainScores, Optional[int], Dict[str, Any]]:
    """Score answers; primary domain from ML with rule-based meta for transparency/fallback."""
    total_score, total_points, correct_count, per_domain = _score_composed_answers(answers)

    domain_names = {
        d.id: d.name
        for d in Domain.objects.filter(id__in=list(per_domain.keys()))
    }
    rule_meta = recommend_rule_based_with_explanation(per_domain, domain_names)
    ml_meta = build_ml_recommendation_meta(per_domain, domain_names)
    ml_primary = ml_meta.get('ml_primary_domain_id')
    rule_primary = rule_meta.get('recommended_domain_id')
    primary_id = ml_primary if ml_primary is not None else rule_primary

    pct_map = ml_meta.get('per_domain_percentages') or {}
    score_summary_parts = []
    for did_str, pct in sorted(pct_map.items(), key=lambda kv: (-float(kv[1]), int(kv[0]))):
        try:
            did = int(did_str)
        except (TypeError, ValueError):
            continue
        name = domain_names.get(did, f'Domain {did}')
        score_summary_parts.append(f'{float(pct):.1f}% {name}')

    recommendation_meta: Dict[str, Any] = {
        **rule_meta,
        'rule_based_recommended_domain_id': rule_primary,
        'recommended_domain_id': primary_id,
        'primary_recommendation_source': (
            'ml_random_forest' if ml_primary is not None else 'rule_based_fallback'
        ),
        'ml_suggested_domain_id': ml_primary,
        'method': 'random_forest',
        'weighted_domain_profile': ml_meta.get('domain_prediction_probabilities', []),
        'weighted_domain_profile_text': ml_meta.get('weighted_domain_profile_text', ''),
        'test_score_by_domain_text': ', '.join(score_summary_parts),
        'ml_primary_domain_id': ml_primary,
        'per_domain_percentages': ml_meta.get('per_domain_percentages', {}),
        'ml_feature_domain_order': ml_meta.get('feature_domain_order', []),
        'ml_classifier_fitted': ml_meta.get('classifier_fitted', False),
    }

    return total_score, total_points, correct_count, per_domain, primary_id, recommendation_meta


def sync_assessment_to_snapshot(attempt_id: int) -> None:
    """
    After skill assessment submit: align StudentProgressSnapshot with this attempt.

    - strongest_domain: first recommended domain on the attempt (if any).
    - domain_weights: normalized % per domain id + metadata['domain_weights'].
    - current_complexity_band: BEGINNER (onboarding baseline after assessment).
    """
    attempt = (
        StudentAssessmentAttempt.objects.filter(pk=attempt_id)
        .prefetch_related('recommended_domains')
        .select_related('user')
        .first()
    )
    if attempt is None:
        return

    snapshot, _ = StudentProgressSnapshot.objects.get_or_create(student=attempt.user)
    primary = attempt.recommended_domains.first()
    weights = extract_domain_weights_from_recommendation_meta(attempt.recommendation_meta)

    snapshot.strongest_domain = primary
    snapshot.domain_weights = weights
    snapshot.current_complexity_band = 'BEGINNER'

    meta = dict(snapshot.metadata) if isinstance(snapshot.metadata, dict) else {}
    meta['domain_weights'] = weights
    meta['assessment_attempt_id'] = attempt.id
    meta['domain_profile_synced_at'] = timezone.now().isoformat()
    snapshot.metadata = meta

    snapshot.save(
        update_fields=[
            'strongest_domain',
            'domain_weights',
            'current_complexity_band',
            'metadata',
            'updated_at',
        ]
    )
