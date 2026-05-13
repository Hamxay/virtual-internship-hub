"""
Hybrid recommender: separate content-based and collaborative feeds (not blended into one score).

Content feed uses cold-start domain weighting or tag/TF-IDF overlap; collaborative uses SVD
when the learner has enough completed projects. Templates respect ``get_allowed_difficulties()``.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from accounts.models import Domain
from projects.models import ProjectTemplate, StudentProgressSnapshot, StudentProjectAssignment
from projects.services.domain_profile import snapshot_domain_weight_percent

logger = logging.getLogger(__name__)

# --- Tunables ---
MIN_RATINGS_FOR_SVD = 12
MIN_DISTINCT_USERS_FOR_SVD = 3
MIN_DISTINCT_ITEMS_FOR_SVD = 3
DOMAIN_WEIGHT_BOOST_COEFF = 0.85
SVD_N_FACTORS = 14
SVD_N_EPOCHS = 20
# Start collaborative suggestions after the first completed project.
MIN_COMPLETED_PROJECTS_FOR_COLLAB = 1
DEFAULT_RECOMMENDATION_TOP_N = 5


def _tags_to_document(tags: Any) -> str:
    if tags is None:
        return ''
    if isinstance(tags, str):
        return tags.strip().lower()
    if isinstance(tags, (list, tuple)):
        return ' '.join(str(t).strip().lower() for t in tags if str(t).strip())
    return str(tags).strip().lower()


def _min_max_normalize(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5] * len(values)
    return [(float(v) - lo) / (hi - lo) for v in values]


def _parse_domain_weights_to_ids(weights: Any) -> List[Tuple[int, float]]:
    if not isinstance(weights, dict) or not weights:
        return []
    out: List[Tuple[int, float]] = []
    for key, raw in weights.items():
        try:
            w = float(raw)
        except (TypeError, ValueError):
            continue
        if w <= 0:
            continue
        did: Optional[int] = None
        try:
            did = int(key)
        except (TypeError, ValueError):
            dom = Domain.objects.filter(name__iexact=str(key).strip()).first()
            if dom is not None:
                did = dom.id
        if did is not None:
            out.append((did, w))
    return out


def _weighted_slots_with_target_coverage(domain_weights: Dict[str, Any], top_n: int) -> List[Tuple[int, int]]:
    if top_n <= 0:
        return []
    pairs = _parse_domain_weights_to_ids(domain_weights)
    if not pairs:
        return []
    sum_w = sum(w for _, w in pairs)
    if sum_w <= 0:
        return []

    domain_count = len(pairs)
    if top_n < domain_count:
        sorted_p = sorted(pairs, key=lambda x: -x[1])
        return [(did, 1) for did, _ in sorted_p[:top_n]]

    slots_map: Dict[int, int] = {did: 1 for did, _ in pairs}
    remaining = top_n - domain_count
    if remaining <= 0:
        return sorted([(d, s) for d, s in slots_map.items() if s > 0], key=lambda x: (-x[1], x[0]))

    triples: List[Tuple[int, int, float]] = []
    for did, w in pairs:
        exact = (w / sum_w) * remaining
        fl = math.floor(exact)
        triples.append((did, fl, exact - float(fl)))
    allocated = sum(t[1] for t in triples)
    remainder_slots = remaining - allocated
    triples.sort(key=lambda t: t[2], reverse=True)
    for i, (did, fl, _) in enumerate(triples):
        slots_map[did] = slots_map.get(did, 0) + fl + (1 if i < remainder_slots else 0)

    return sorted([(d, s) for d, s in slots_map.items() if s > 0], key=lambda x: (-x[1], x[0]))


def _behavioral_pick_per_domain_quotas(
    scored: List[Tuple[ProjectTemplate, float, Dict[str, Any]]],
    snapshot: StudentProgressSnapshot,
    user,
    top_n: int,
) -> List[Tuple[ProjectTemplate, float, Dict[str, Any]]]:
    target_ids = get_student_target_domain_ids(user)
    if not target_ids or top_n <= 0:
        scored.sort(key=lambda row: row[1], reverse=True)
        return scored[:top_n]

    weights = _domain_weights_for_targets(snapshot, target_ids)
    if not weights:
        weights = {str(d): 1.0 for d in target_ids}

    slot_plan = _weighted_slots_with_target_coverage(weights, top_n)
    by_domain: Dict[int, List[Tuple[ProjectTemplate, float, Dict[str, Any]]]] = defaultdict(list)
    for row in scored:
        by_domain[row[0].domain_id].append(row)
    for did in by_domain:
        by_domain[did].sort(key=lambda row: row[1], reverse=True)

    picked: List[Tuple[ProjectTemplate, float, Dict[str, Any]]] = []
    seen: Set[int] = set()
    for domain_id, slots in slot_plan:
        for row in by_domain.get(domain_id, [])[:slots]:
            template_pk = row[0].pk
            if template_pk not in seen:
                picked.append(row)
                seen.add(template_pk)

    if len(picked) < top_n:
        scored.sort(key=lambda row: row[1], reverse=True)
        for row in scored:
            if len(picked) >= top_n:
                break
            template_pk = row[0].pk
            if template_pk not in seen:
                picked.append(row)
                seen.add(template_pk)

    picked.sort(key=lambda row: row[1], reverse=True)
    return picked[:top_n]


def get_student_target_domain_ids(user) -> set[int]:
    profile = getattr(user, 'student_profile', None)
    if profile is None:
        return set()
    return set(profile.target_domains.values_list('id', flat=True))


def _raw_domain_weights_dict(snapshot: StudentProgressSnapshot) -> Dict[str, Any]:
    weights = snapshot.domain_weights if isinstance(snapshot.domain_weights, dict) else {}
    if weights:
        return weights
    meta = snapshot.metadata if isinstance(snapshot.metadata, dict) else {}
    inner = meta.get('domain_weights')
    return inner if isinstance(inner, dict) else {}


def _domain_weights_for_targets(
    snapshot: StudentProgressSnapshot,
    target_domain_ids: set[int],
) -> Dict[str, float]:
    raw = _raw_domain_weights_dict(snapshot)
    pairs = _parse_domain_weights_to_ids(raw)
    if not target_domain_ids:
        return {str(d): float(w) for d, w in pairs} if pairs else {}
    filtered = [(d, w) for d, w in pairs if d in target_domain_ids]
    if not filtered:
        return {str(d): 1.0 for d in target_domain_ids}
    total = sum(w for _, w in filtered)
    if total <= 1e-12:
        return {str(d): 1.0 for d in target_domain_ids}
    return {str(d): float(w) / total * 100.0 for d, w in filtered}


def resolve_recommendation_top_n(user=None, snapshot: Optional[StudentProgressSnapshot] = None) -> int:
    return DEFAULT_RECOMMENDATION_TOP_N


def _assigned_template_ids_for_student(user) -> Set[int]:
    return set(
        StudentProjectAssignment.objects.filter(student=user).values_list(
            'project_template_id', flat=True
        )
    )


def _cold_start_feed_tuples(
    user,
    snapshot: StudentProgressSnapshot,
    top_n: int,
    allowed_complexities: List[str],
) -> List[Tuple[ProjectTemplate, float, Dict[str, Any]]]:
    if top_n <= 0:
        return []

    target_ids = get_student_target_domain_ids(user)
    weights = _domain_weights_for_targets(snapshot, target_ids)
    if not weights and not target_ids:
        pairs = _parse_domain_weights_to_ids(_raw_domain_weights_dict(snapshot))
        weights = {str(d): float(w) for d, w in pairs}
    if not weights:
        return []

    slot_plan = _weighted_slots_with_target_coverage(weights, top_n)
    if not slot_plan:
        return []

    assigned_template_ids = _assigned_template_ids_for_student(user)
    weight_by_id = {did: w for did, w in _parse_domain_weights_to_ids(weights)}
    slot_plan.sort(key=lambda item: (-weight_by_id.get(item[0], 0.0), item[0]))

    rows: List[Tuple[ProjectTemplate, float, Dict[str, Any]]] = []
    for domain_id, slots in slot_plan:
        if slots <= 0:
            continue
        queryset = (
            ProjectTemplate.objects.filter(
                active=True,
                domain_id=domain_id,
                complexity__in=allowed_complexities,
            )
            .exclude(pk__in=assigned_template_ids)
            .select_related('domain')
            .order_by('title', 'pk')
        )
        for template in queryset[:slots]:
            weight_percent = weights.get(str(domain_id))
            if weight_percent is None:
                weight_percent = snapshot_domain_weight_percent(snapshot, domain_id)
            rows.append(
                (
                    template,
                    1.0,
                    {
                        'mode': 'cold_start',
                        'domain_id': domain_id,
                        'domain_weight_percent': round(float(weight_percent), 2) if weight_percent is not None else None,
                    },
                )
            )
            assigned_template_ids.add(template.pk)

    return rows[:top_n]


def _content_tag_feed_tuples(
    user,
    snapshot: StudentProgressSnapshot,
    top_n: int,
    allowed_complexities: List[str],
) -> List[Tuple[ProjectTemplate, float, Dict[str, Any]]]:
    meta = snapshot.metadata if isinstance(snapshot.metadata, dict) else {}
    successful_tags = meta.get('successful_tags') or []
    if not isinstance(successful_tags, list):
        successful_tags = []

    assigned_template_ids = _assigned_template_ids_for_student(user)
    target_ids = get_student_target_domain_ids(user)
    queryset = (
        ProjectTemplate.objects.filter(active=True, complexity__in=allowed_complexities)
        .exclude(pk__in=assigned_template_ids)
        .select_related('domain')
    )
    if target_ids:
        queryset = queryset.filter(domain_id__in=target_ids)
    candidates = list(queryset)
    if not candidates:
        return []

    user_doc = _tags_to_document(successful_tags)
    project_docs = [_tags_to_document(template.tags) for template in candidates]
    candidate_count = len(candidates)

    if user_doc:
        try:
            corpus = [user_doc] + project_docs
            vectorizer = TfidfVectorizer(
                min_df=1,
                lowercase=True,
                token_pattern=r'(?u)\b\w\w+\b',
            )
            matrix = vectorizer.fit_transform(corpus)
            user_vec = matrix[0:1]
            project_matrix = matrix[1:]
            raw_similarities = cosine_similarity(user_vec, project_matrix).flatten()
            content_similarity = [float(x) for x in raw_similarities]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('TF-IDF / cosine similarity failed: %s', exc)
            content_similarity = [0.0] * candidate_count
    else:
        content_similarity = [0.0] * candidate_count

    content_boosted: List[float] = []
    for template, base_similarity in zip(candidates, content_similarity):
        domain_weight = snapshot_domain_weight_percent(snapshot, template.domain_id)
        if domain_weight is None or domain_weight <= 0 or base_similarity <= 0:
            content_boosted.append(base_similarity)
            continue
        factor = 1.0 + DOMAIN_WEIGHT_BOOST_COEFF * (float(domain_weight) / 100.0)
        boosted = min(base_similarity * factor, 1.0)
        content_boosted.append(boosted)

    content_norm = _min_max_normalize(content_boosted)
    scored_rows: List[Tuple[ProjectTemplate, float, Dict[str, Any]]] = []
    for index, template in enumerate(candidates):
        scored_rows.append(
            (
                template,
                round(content_norm[index], 6),
                {
                    'mode': 'content_tags',
                    'content_similarity': round(content_similarity[index], 6),
                    'content_boosted': round(content_boosted[index], 6),
                    'content_norm': round(content_norm[index], 6),
                },
            )
        )

    return _behavioral_pick_per_domain_quotas(scored_rows, snapshot, user, top_n)


def _collaborative_feed_tuples(
    user,
    snapshot: StudentProgressSnapshot,
    top_n: int,
    allowed_complexities: List[str],
    exclude_template_ids: Set[int],
) -> List[Tuple[ProjectTemplate, float, Dict[str, Any]]]:
    if top_n <= 0:
        return []

    assigned_template_ids = _assigned_template_ids_for_student(user)
    blocked_ids = assigned_template_ids | exclude_template_ids
    target_ids = get_student_target_domain_ids(user)
    queryset = (
        ProjectTemplate.objects.filter(active=True, complexity__in=allowed_complexities)
        .exclude(pk__in=blocked_ids)
        .select_related('domain')
    )
    if target_ids:
        queryset = queryset.filter(domain_id__in=target_ids)
    candidates = list(queryset)
    if not candidates:
        return []

    raw_scores = _surprise_svd_predict_scores(user, candidates)
    indexed = list(enumerate(candidates))
    indexed.sort(key=lambda pair: raw_scores[pair[0]], reverse=True)

    rows: List[Tuple[ProjectTemplate, float, Dict[str, Any]]] = []
    for rank_index, (candidate_index, template) in enumerate(indexed):
        if rank_index >= top_n:
            break
        collaborative_raw = round(float(raw_scores[candidate_index]), 4)
        normalized_collaborative = max(0.0, min(1.0, collaborative_raw / 100.0))
        rows.append(
            (
                template,
                normalized_collaborative,
                {
                    'mode': 'collaborative',
                    'collaborative_raw': collaborative_raw,
                },
            )
        )
    return rows


def _surprise_svd_predict_scores(user, candidates: Sequence[ProjectTemplate]) -> List[float]:
    candidate_count = len(candidates)
    rows = list(
        StudentProjectAssignment.objects.filter(latest_evaluation_score__isnull=False).values_list(
            'student_id', 'project_template_id', 'latest_evaluation_score'
        )
    )
    if len(rows) < MIN_RATINGS_FOR_SVD:
        return [0.0] * candidate_count

    user_ids = {int(r[0]) for r in rows}
    item_ids = {int(r[1]) for r in rows}
    if len(user_ids) < MIN_DISTINCT_USERS_FOR_SVD or len(item_ids) < MIN_DISTINCT_ITEMS_FOR_SVD:
        return [0.0] * candidate_count

    uid = int(user.pk)
    if uid not in user_ids:
        return [0.0] * candidate_count

    try:
        import pandas as pd
        from surprise import Dataset, Reader, SVD
    except ImportError:
        logger.warning('pandas and/or scikit-surprise not installed; collaborative score is 0.')
        return [0.0] * candidate_count

    dataframe = pd.DataFrame(rows, columns=('user', 'item', 'rating'))
    dataframe['user'] = dataframe['user'].astype(int)
    dataframe['item'] = dataframe['item'].astype(int)
    dataframe['rating'] = dataframe['rating'].astype(float)

    reader = Reader(rating_scale=(0, 100))
    data = Dataset.load_from_df(dataframe[['user', 'item', 'rating']], reader)
    trainset = data.build_full_trainset()
    n_factors = min(SVD_N_FACTORS, max(1, min(len(user_ids), len(item_ids)) - 1))
    algorithm = SVD(
        n_factors=n_factors,
        n_epochs=SVD_N_EPOCHS,
        random_state=42,
        verbose=False,
    )
    try:
        algorithm.fit(trainset)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning('Surprise SVD fit failed: %s', exc)
        return [0.0] * candidate_count

    out: List[float] = []
    for template in candidates:
        item_id = int(template.pk)
        try:
            prediction = algorithm.predict(uid, item_id)
            estimated = float(prediction.est)
            estimated = max(0.0, min(100.0, estimated))
        except Exception:
            estimated = 0.0
        out.append(estimated)
    return out


class HybridRecommender:
    """
    Produces two independent ranked feeds (no blended score between TF-IDF and SVD).
    """

    def collect_separated_feeds(
        self,
        user,
        top_n: Optional[int] = None,
    ) -> Dict[str, List[Tuple[ProjectTemplate, float, Dict[str, Any]]]]:
        """
        Internal: template, ranking weight (0–1 scale where applicable), and breakdown dict per row.
        """
        snapshot, _ = StudentProgressSnapshot.objects.get_or_create(student=user)
        if top_n is None:
            top_n = resolve_recommendation_top_n(user, snapshot)
        if top_n <= 0:
            return {'content_based': [], 'collaborative': []}

        allowed_complexities = snapshot.get_allowed_difficulties()
        has_completed = StudentProjectAssignment.objects.filter(
            student=user,
            status='COMPLETED',
        ).exists()

        if not has_completed:
            content_rows = _cold_start_feed_tuples(user, snapshot, top_n, allowed_complexities)
        else:
            content_rows = _content_tag_feed_tuples(user, snapshot, top_n, allowed_complexities)

        content_template_ids = {row[0].pk for row in content_rows}
        collaborative_rows: List[Tuple[ProjectTemplate, float, Dict[str, Any]]] = []
        if int(snapshot.completed_projects or 0) >= MIN_COMPLETED_PROJECTS_FOR_COLLAB:
            collaborative_rows = _collaborative_feed_tuples(
                user,
                snapshot,
                top_n,
                allowed_complexities,
                content_template_ids,
            )

        return {
            'content_based': content_rows,
            'collaborative': collaborative_rows,
        }
