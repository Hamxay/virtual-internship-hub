from collections import defaultdict
from statistics import mean

from django.utils import timezone

from accounts.models import Domain
from assessments.models import StudentAssessmentAttempt
from projects.models import (
    ProjectTemplate,
    StudentProgressSnapshot,
    StudentProjectAssignment,
)


COMPLEXITY_ORDER = {
    'BEGINNER': 0,
    'INTERMEDIATE': 1,
    'ADVANCED': 2,
}

SKILL_TO_COMPLEXITY = {
    'BEGINNER': 'BEGINNER',
    'INTERMEDIATE': 'INTERMEDIATE',
    'ADVANCED': 'ADVANCED',
    'EXPERT': 'ADVANCED',
}


def _safe_percentage(attempt, domain_id):
    ranked = (attempt.recommendation_meta or {}).get('ranked_domains') or []
    for item in ranked:
        if int(item.get('domain_id', 0)) == int(domain_id):
            return float(item.get('percentage', 0))
    return 0.0


def infer_student_complexity_band(student, snapshot=None):
    if snapshot and snapshot.completed_projects >= 3 and snapshot.average_score >= 80:
        if snapshot.current_complexity_band == 'ADVANCED':
            return 'ADVANCED'
        if snapshot.average_score >= 85:
            return 'ADVANCED'
        return 'INTERMEDIATE'

    profile = getattr(student, 'student_profile', None)
    if profile and profile.current_skill_level:
        return SKILL_TO_COMPLEXITY.get(profile.current_skill_level, 'BEGINNER')
    return 'BEGINNER'


def update_student_progress_snapshot(student):
    assignments = list(
        StudentProjectAssignment.objects.filter(student=student)
        .select_related('project_template__domain')
        .order_by('-assigned_at')
    )
    scored = [a for a in assignments if a.latest_evaluation_score is not None]
    average_score = round(mean(a.latest_evaluation_score for a in scored), 2) if scored else 0.0

    domain_scores = defaultdict(list)
    for assignment in scored:
        domain_scores[assignment.project_template.domain_id].append(assignment.latest_evaluation_score)

    strongest_domain = None
    if domain_scores:
        best_domain_id = max(
            domain_scores,
            key=lambda domain_id: mean(domain_scores[domain_id]),
        )
        strongest_domain = Domain.objects.filter(id=best_domain_id).first()

    if average_score >= 85 and len(scored) >= 4:
        complexity = 'ADVANCED'
    elif average_score >= 70 and len(scored) >= 2:
        complexity = 'INTERMEDIATE'
    else:
        complexity = infer_student_complexity_band(student)

    snapshot, _ = StudentProgressSnapshot.objects.get_or_create(student=student)
    snapshot.strongest_domain = strongest_domain
    snapshot.completed_projects = sum(1 for a in assignments if a.status == 'COMPLETED')
    snapshot.average_score = average_score
    snapshot.current_complexity_band = complexity
    snapshot.metadata = StudentProgressSnapshot.build_metadata(scored)
    snapshot.save()
    return snapshot


def _latest_assessment(student):
    return (
        StudentAssessmentAttempt.objects.filter(user=student)
        .prefetch_related('recommended_domains', 'test_domains')
        .order_by('-submitted_at')
        .first()
    )


def _domain_match_score(template, target_domain_ids, recommended_domain_id):
    if recommended_domain_id and template.domain_id == recommended_domain_id:
        return 100.0
    if template.domain_id in target_domain_ids:
        return 82.0
    return 35.0 if not target_domain_ids else 15.0


def _difficulty_fit_score(template, inferred_band, snapshot):
    target_rank = COMPLEXITY_ORDER.get(inferred_band, 0)
    template_rank = COMPLEXITY_ORDER.get(template.complexity, 0)
    gap = template_rank - target_rank
    if gap == 0:
        return 100.0
    if gap == -1:
        return 76.0
    if gap == 1 and snapshot.average_score >= 78:
        return 84.0
    if gap == 1:
        return 55.0
    if gap >= 2:
        return 28.0
    return 48.0


def _progress_readiness_score(template, snapshot, domain_history):
    completed_in_domain = domain_history.get(template.domain_id, 0)
    if completed_in_domain == 0:
        return 65.0
    if snapshot.average_score >= 80:
        return 90.0
    if snapshot.average_score >= 65:
        return 72.0
    return 52.0


def _diversity_penalty(template, assigned_template_ids, completed_template_ids):
    if template.id in completed_template_ids:
        return 55.0
    if template.id in assigned_template_ids:
        return 25.0
    return 0.0


def refresh_recommended_assignments(student, limit=5):
    snapshot = update_student_progress_snapshot(student)
    latest_assessment = _latest_assessment(student)
    profile = getattr(student, 'student_profile', None)
    target_domain_ids = set(profile.target_domains.values_list('id', flat=True)) if profile else set()
    recommended_domain_id = None
    if latest_assessment:
        recommended = latest_assessment.recommended_domains.first()
        recommended_domain_id = recommended.id if recommended else None

    active_assignments = StudentProjectAssignment.objects.filter(
        student=student,
    ).exclude(status='COMPLETED')
    assigned_template_ids = set(active_assignments.values_list('project_template_id', flat=True))
    completed_template_ids = set(
        StudentProjectAssignment.objects.filter(
            student=student,
            status='COMPLETED',
        ).values_list('project_template_id', flat=True)
    )

    domain_history = defaultdict(int)
    for assignment in StudentProjectAssignment.objects.filter(student=student, status='COMPLETED').select_related('project_template'):
        domain_history[assignment.project_template.domain_id] += 1

    inferred_band = infer_student_complexity_band(student, snapshot=snapshot)

    templates = ProjectTemplate.objects.filter(active=True).select_related('domain', 'instruction', 'rubric')
    if target_domain_ids:
        templates = templates.filter(domain_id__in=target_domain_ids | ({recommended_domain_id} if recommended_domain_id else set()))

    scored_candidates = []
    for template in templates:
        if template.id in completed_template_ids:
            continue
        if template.id in assigned_template_ids and template.id not in completed_template_ids:
            continue

        domain_match = _domain_match_score(template, target_domain_ids, recommended_domain_id)
        assessment_strength = _safe_percentage(latest_assessment, template.domain_id) if latest_assessment else 55.0
        progress_readiness = _progress_readiness_score(template, snapshot, domain_history)
        difficulty_fit = _difficulty_fit_score(template, inferred_band, snapshot)
        diversity_penalty = _diversity_penalty(template, assigned_template_ids, completed_template_ids)
        recommendation_score = round(
            (domain_match * 0.35)
            + (assessment_strength * 0.25)
            + (progress_readiness * 0.20)
            + (difficulty_fit * 0.20)
            - diversity_penalty,
            2,
        )
        scored_candidates.append(
            (
                recommendation_score,
                template,
                {
                    'domain_match_score': round(domain_match, 2),
                    'assessment_strength_score': round(assessment_strength, 2),
                    'progress_readiness_score': round(progress_readiness, 2),
                    'difficulty_fit_score': round(difficulty_fit, 2),
                    'diversity_penalty': round(diversity_penalty, 2),
                },
            )
        )

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    selected = scored_candidates[:limit]
    results = []
    for score, template, breakdown in selected:
        reason_text = (
            f'{template.domain.name} is a strong fit right now. '
            f'Domain match {breakdown["domain_match_score"]:.0f}, '
            f'assessment strength {breakdown["assessment_strength_score"]:.0f}, '
            f'difficulty fit {breakdown["difficulty_fit_score"]:.0f}.'
        )
        assignment, created = StudentProjectAssignment.objects.get_or_create(
            student=student,
            project_template=template,
            defaults={
                'status': 'RECOMMENDED',
                'recommended_by': 'AI',
                'recommendation_score': score,
                'recommendation_reason': reason_text,
            },
        )
        if not created and assignment.status == 'RECOMMENDED':
            assignment.recommended_by = 'AI'
            assignment.recommendation_score = score
            assignment.recommendation_reason = reason_text
            assignment.save(
                update_fields=['recommended_by', 'recommendation_score', 'recommendation_reason'],
            )
        results.append(assignment)

    snapshot.last_recommended_at = timezone.now()
    snapshot.save(update_fields=['last_recommended_at', 'updated_at'])
    return results
