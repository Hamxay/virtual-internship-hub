from collections import defaultdict
from statistics import mean

from django.utils import timezone

from accounts.models import Domain
from projects.models import StudentProgressSnapshot, StudentProjectAssignment
from projects.services.domain_profile import ASSESSMENT_SNAPSHOT_META_KEYS
from projects.services.hybrid_recommender import HybridRecommender, resolve_recommendation_top_n


def _successful_tags_from_completed_assignments(assignments):
    """Distinct template tags from completed work, first-seen order, case-folded uniqueness."""
    seen = set()
    out = []
    for assignment in assignments:
        if assignment.status != 'COMPLETED':
            continue
        tags = getattr(assignment.project_template, 'tags', None) or []
        if not isinstance(tags, list):
            continue
        for raw in tags:
            label = str(raw).strip()
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
    return out

SKILL_TO_COMPLEXITY = {
    'BEGINNER': 'BEGINNER',
    'INTERMEDIATE': 'INTERMEDIATE',
    'ADVANCED': 'ADVANCED',
    'EXPERT': 'ADVANCED',
}

COMPLEXITY_RANK = {
    'BEGINNER': 0,
    'INTERMEDIATE': 1,
    'ADVANCED': 2,
}


def apply_recommended_difficulty_if_higher(student, recommended_raw: str) -> None:
    """Bump the learner's complexity band when the model suggests a harder level than the snapshot."""
    rec = str(recommended_raw or 'BEGINNER').upper().strip()
    if rec not in COMPLEXITY_RANK:
        rec = 'BEGINNER'
    snapshot = StudentProgressSnapshot.objects.filter(student=student).first()
    if not snapshot:
        return
    cur = str(snapshot.current_complexity_band or 'BEGINNER').upper().strip()
    if cur not in COMPLEXITY_RANK:
        cur = 'BEGINNER'
    if COMPLEXITY_RANK[rec] <= COMPLEXITY_RANK[cur]:
        return
    snapshot.current_complexity_band = rec
    prev_meta = snapshot.metadata if isinstance(snapshot.metadata, dict) else {}
    snapshot.metadata = {
        **prev_meta,
        'recommended_next_difficulty': rec,
    }
    snapshot.save(update_fields=['current_complexity_band', 'metadata', 'updated_at'])


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
    base_meta = StudentProgressSnapshot.build_metadata(scored)
    successful_tags = _successful_tags_from_completed_assignments(assignments)
    prev = snapshot.metadata if isinstance(snapshot.metadata, dict) else {}
    assessment_meta_preserve = {k: prev[k] for k in ASSESSMENT_SNAPSHOT_META_KEYS if k in prev}
    snapshot.metadata = {
        **base_meta,
        'successful_tags': successful_tags,
        **assessment_meta_preserve,
    }
    snapshot.save()
    return snapshot


def _build_content_feed_reason(template, breakdown: dict) -> str:
    if breakdown.get('mode') == 'cold_start':
        domain_weight = breakdown.get('domain_weight_percent')
        weight_label = (
            f'{domain_weight:.0f}% domain fit' if domain_weight is not None else 'assessment-aligned domain'
        )
        return (
            f'Starter project matched to your assessment weights ({weight_label}). '
            f'Domain: {template.domain.name}.'
        )

    content_norm = breakdown.get('content_norm', 0.0)
    reason_parts = [
        f'Content-based match (your completed project tags; score {content_norm:.2f}).',
    ]
    if breakdown.get('content_similarity', 0) > 0:
        reason_parts.append(f'Tag overlap {breakdown["content_similarity"]:.2f}.')
    return ' '.join(reason_parts)


def refresh_recommended_assignments(student, limit=None):
    """Replace all RECOMMENDED rows with a fresh content-based and collaborative feed."""
    snapshot = update_student_progress_snapshot(student)
    if limit is None:
        limit = resolve_recommendation_top_n(student, snapshot)

    StudentProjectAssignment.objects.filter(
        student=student,
        status='RECOMMENDED',
    ).delete()

    recommender = HybridRecommender()
    feeds_with_scores = recommender.collect_separated_feeds(student, top_n=limit)

    for template, normalized_score, breakdown in feeds_with_scores['content_based']:
        if breakdown.get('mode') == 'cold_start':
            recommendation_source = 'COLD_START'
            recommendation_score = 100.0
        else:
            recommendation_source = 'CONTENT_BASED'
            recommendation_score = round(float(normalized_score) * 100.0, 2)

        StudentProjectAssignment.objects.create(
            student=student,
            project_template=template,
            status='RECOMMENDED',
            recommended_by='AI',
            recommendation_score=recommendation_score,
            recommendation_reason=_build_content_feed_reason(template, breakdown),
            recommendation_source=recommendation_source,
        )

    for template, _normalized_score, breakdown in feeds_with_scores['collaborative']:
        collaborative_raw = float(breakdown.get('collaborative_raw', 0.0))
        reason_text = (
            f'Collaborative filtering (predicted performance ~{collaborative_raw:.1f}/100). '
            f'Domain: {template.domain.name}.'
        )
        StudentProjectAssignment.objects.create(
            student=student,
            project_template=template,
            status='RECOMMENDED',
            recommended_by='AI',
            recommendation_score=round(collaborative_raw, 2),
            recommendation_reason=reason_text,
            recommendation_source='COLLABORATIVE',
        )

    snapshot.last_recommended_at = timezone.now()
    snapshot.save(update_fields=['last_recommended_at', 'updated_at'])
