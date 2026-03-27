"""
FR2: Scikit-learn–based domain recommendation (ML only).
Loads model_domain_recommender.joblib; no rule-based fallback.
Train with: python manage.py train_domain_recommender
"""
from pathlib import Path
from typing import List, Optional, Tuple

from .ai_recommendation import DomainScores

NUM_FEATURES = 3
_MODEL_CACHE = None
_MODEL_PATH = Path(__file__).resolve().parent / "model_domain_recommender.joblib"


def _build_features_and_domain_order(per_domain_scores: DomainScores) -> Tuple[List[float], List[int]]:
    """Build feature vector [pct1, pct2, pct3] and ordered domain_ids for mapping prediction index back."""
    if not per_domain_scores:
        return [0.0] * NUM_FEATURES, []
    sorted_ids = sorted(per_domain_scores.keys())
    domain_ids = sorted_ids[:NUM_FEATURES]
    features = []
    for did in domain_ids:
        score, total = per_domain_scores[did]
        pct = (score / total * 100.0) if total else 0.0
        features.append(pct)
    while len(features) < NUM_FEATURES:
        features.append(0.0)
    return features, domain_ids


def _load_model():
    """Load and cache the joblib model; return None if missing or on error."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    if not _MODEL_PATH.exists():
        return None
    try:
        import joblib
        _MODEL_CACHE = joblib.load(_MODEL_PATH)
        return _MODEL_CACHE
    except Exception:
        return None


def recommend_one_domain_ml(per_domain_scores: DomainScores) -> Optional[int]:
    """
    Recommend one domain using the Scikit-learn model only.
    Returns None if scores are empty, only one domain (use that domain), model missing,
    or prediction fails / index out of range.
    """
    if not per_domain_scores:
        return None
    features, domain_ids = _build_features_and_domain_order(per_domain_scores)
    if not domain_ids:
        return None
    if len(domain_ids) == 1:
        return domain_ids[0]
    model = _load_model()
    if model is None:
        return None
    try:
        X = [features]
        pred = model.predict(X)
        idx = int(pred[0])
        if 0 <= idx < len(domain_ids):
            return domain_ids[idx]
    except Exception:
        return None
    return None
