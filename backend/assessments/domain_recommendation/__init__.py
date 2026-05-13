"""Domain recommendation: rule-based ranking plus RandomForest weights for metadata."""

from .rule_based_ranking import (
    DomainScores,
    recommend_one_domain,
    recommend_rule_based_with_explanation,
)
from .sklearn_domain_classifier import (
    DomainAptitudeClassifier,
    build_ml_recommendation_meta,
    generate_dummy_xy_for_domains,
)

__all__ = [
    'DomainScores',
    'DomainAptitudeClassifier',
    'build_ml_recommendation_meta',
    'generate_dummy_xy_for_domains',
    'recommend_one_domain',
    'recommend_rule_based_with_explanation',
]
