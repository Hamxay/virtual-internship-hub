"""
Domain aptitude weights from skill assessment metadata and snapshot.domain_weights.
Snapshot rows are updated from assessments.services.sync_assessment_to_snapshot.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from projects.models import StudentProgressSnapshot

# Merged into progress snapshot metadata; includes legacy keys for older DB rows.
ASSESSMENT_SNAPSHOT_META_KEYS: Tuple[str, ...] = (
    'domain_weights',
    'assessment_attempt_id',
    'domain_profile_synced_at',
    'fr2_assessment_attempt_id',
    'fr2_synced_at',
)


def extract_domain_weights_from_recommendation_meta(meta: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """
    Build {str(domain_id): weight_percent} summing to ~100.

    Prefers weighted_domain_profile (ML); else normalizes ranked_domains percentages.
    """
    meta = meta or {}
    profiles = meta.get('weighted_domain_profile')
    if profiles and isinstance(profiles, list):
        raw: Dict[str, float] = {}
        for item in profiles:
            if not isinstance(item, dict):
                continue
            did = item.get('domain_id')
            if did is None:
                continue
            wp = float(item.get('weight_percent', 0) or 0)
            raw[str(int(did))] = max(0.0, wp)
        return _normalize_to_100(raw)

    ranked = meta.get('ranked_domains') or []
    raw = {}
    for item in ranked:
        if not isinstance(item, dict):
            continue
        did = item.get('domain_id')
        if did is None:
            continue
        raw[str(int(did))] = float(item.get('percentage', 0) or 0)
    return _normalize_to_100(raw)


def _normalize_to_100(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {k: round(v / total * 100.0, 2) for k, v in weights.items()}


def snapshot_domain_weight_percent(
    snapshot: Optional[StudentProgressSnapshot],
    domain_id: int,
) -> Optional[float]:
    """
    Weight 0–100 for domain_id from snapshot.domain_weights, or None if unset.
    """
    if snapshot is None:
        return None
    w = snapshot.domain_weights or {}
    if not w:
        return None
    return float(w.get(str(int(domain_id)), 0.0))
