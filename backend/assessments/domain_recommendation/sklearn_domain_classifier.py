"""RandomForest over per-domain percentages → primary domain + weights for ``recommendation_meta``."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier


def _percentages_from_domain_scores(
    per_domain_scores: Mapping[int, Tuple[int, int]],
) -> Dict[int, float]:
    """Map {domain_id: (earned_points, total_points)} -> {domain_id: percentage}."""
    out: Dict[int, float] = {}
    for domain_id, (score, total) in per_domain_scores.items():
        if total <= 0:
            continue
        out[int(domain_id)] = round((score / total) * 100.0, 4)
    return out


def generate_dummy_xy_for_domains(
    domain_ids: Sequence[int],
    n_samples_per_class: int = 20,
    random_state: int = 42,
) -> Tuple[List[List[float]], List[int]]:
    """Synthetic supervised data for a fixed set of domain ids (demo / cold start)."""
    ids = sorted({int(d) for d in domain_ids})
    n = len(ids)
    if n == 0:
        return [], []

    rng = np.random.default_rng(random_state)
    X: List[List[float]] = []
    y: List[int] = []

    for label_domain in ids:
        label_idx = ids.index(label_domain)
        for _ in range(n_samples_per_class):
            row = rng.uniform(25.0, 55.0, size=n).tolist()
            row[label_idx] = float(rng.uniform(72.0, 98.0))
            if rng.random() < 0.15:
                j = int(rng.integers(0, n))
                if j != label_idx:
                    row[j] = float(rng.uniform(60.0, 85.0))
            X.append(row)
            y.append(label_domain)

    return X, y


class DomainAptitudeClassifier:
    """
    RandomForest primary-domain predictor with probability-derived weights.

    Features: one column per domain_id (sorted), values = percentage scores for the attempt.
    Labels: integer domain ids (sklearn classes_).
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: Optional[int] = None,
        random_state: int = 42,
        n_jobs: int = -1,
    ) -> None:
        self._rf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            n_jobs=n_jobs,
        )
        self.feature_domain_ids: Tuple[int, ...] = ()
        self._is_fitted = False

    def fit(
        self,
        X: Iterable[Sequence[float]],
        y: Sequence[int],
        feature_domain_ids: Sequence[int],
    ) -> DomainAptitudeClassifier:
        self.feature_domain_ids = tuple(sorted({int(d) for d in feature_domain_ids}))
        x_arr = np.asarray(list(X), dtype=float)
        if x_arr.ndim != 2 or x_arr.shape[1] != len(self.feature_domain_ids):
            raise ValueError(
                "X must be 2D with one column per entry in feature_domain_ids."
            )
        self._rf.fit(x_arr, np.asarray(list(y), dtype=int))
        self._is_fitted = True
        return self

    def fit_dummy_synthetic(
        self,
        domain_ids: Sequence[int],
        n_samples_per_class: int = 20,
        random_state: int = 42,
    ) -> DomainAptitudeClassifier:
        X, y = generate_dummy_xy_for_domains(
            domain_ids,
            n_samples_per_class=n_samples_per_class,
            random_state=random_state,
        )
        if not X:
            self._is_fitted = False
            self.feature_domain_ids = tuple()
            return self
        self.feature_domain_ids = tuple(sorted({int(d) for d in domain_ids}))
        self._rf.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=int))
        self._is_fitted = True
        return self

    def _row_from_percentages(self, per_domain_percentage: Mapping[int, float]) -> np.ndarray:
        return np.array(
            [[float(per_domain_percentage.get(did, 0.0)) for did in self.feature_domain_ids]],
            dtype=float,
        )

    def predict_primary_and_probabilities(
        self,
        per_domain_percentage: Mapping[int, float],
        domain_names: Optional[Mapping[int, str]] = None,
    ) -> Dict[str, Any]:
        domain_names = domain_names or {}
        ids = sorted({int(k) for k in per_domain_percentage.keys()})
        if not ids:
            return {
                "ml_primary_domain_id": None,
                "domain_prediction_probabilities": [],
                "weighted_domain_profile_text": "",
                "classifier_fitted": False,
            }

        if len(ids) == 1:
            only = ids[0]
            name = domain_names.get(only, f"Domain {only}")
            return {
                "ml_primary_domain_id": only,
                "domain_prediction_probabilities": [
                    {
                        "domain_id": only,
                        "domain_name": name,
                        "probability": 1.0,
                        "weight_percent": 100.0,
                    }
                ],
                "weighted_domain_profile_text": f"100% {name}",
                "classifier_fitted": False,
                "note": "single_test_domain_degenerate_case",
            }

        if (
            not self._is_fitted
            or tuple(sorted(ids)) != tuple(self.feature_domain_ids)
        ):
            self.fit_dummy_synthetic(ids)

        row = self._row_from_percentages(per_domain_percentage)
        primary = int(self._rf.predict(row)[0])
        proba = self._rf.predict_proba(row)[0]
        classes = [int(c) for c in self._rf.classes_]

        entries: List[Dict[str, Any]] = []
        for domain_id, p in zip(classes, proba):
            w = round(float(p) * 100.0, 2)
            entries.append(
                {
                    "domain_id": domain_id,
                    "domain_name": domain_names.get(domain_id, f"Domain {domain_id}"),
                    "probability": round(float(p), 6),
                    "weight_percent": w,
                }
            )
        entries.sort(key=lambda e: (-e["weight_percent"], e["domain_id"]))

        # Always list every class so a 3-domain test never hides the weakest bucket
        # (previously entries under 1% were omitted and the profile looked 2-way only).
        parts = [f"{e['weight_percent']:.1f}% {e['domain_name']}" for e in entries]

        return {
            "ml_primary_domain_id": primary,
            "domain_prediction_probabilities": entries,
            "weighted_domain_profile_text": ", ".join(parts),
            "classifier_fitted": True,
        }


def build_ml_recommendation_meta(
    per_domain_scores: Mapping[int, Tuple[int, int]],
    domain_names: Mapping[int, str],
    classifier: Optional[DomainAptitudeClassifier] = None,
) -> Dict[str, Any]:
    """Build ML fields to merge into recommendation_meta from composed-test score tuples."""
    clf = classifier or DomainAptitudeClassifier()
    pct = _percentages_from_domain_scores(per_domain_scores)
    ml_part = clf.predict_primary_and_probabilities(pct, domain_names=domain_names)
    return {
        **ml_part,
        "per_domain_percentages": {str(k): v for k, v in sorted(pct.items())},
        "feature_domain_order": list(clf.feature_domain_ids),
    }
