"""
FR2: Rule-based domain recommendation from per-domain assessment scores.
Highest percentage (earned points / total points) wins; ties broken by lower domain id.
"""
from typing import Any, Dict, List, Optional

# Per-domain: (score, total_points) -> percentage
DomainScores = Dict[int, tuple[int, int]]


def recommend_one_domain(per_domain_scores: DomainScores) -> Optional[int]:
    """
    Recommend a single domain that is the best fit (highest performance).
    """
    if not per_domain_scores:
        return None

    best_domain_id: Optional[int] = None
    best_percentage: float = -1.0

    for domain_id, (score, total) in per_domain_scores.items():
        if total <= 0:
            continue
        pct = (score / total) * 100
        if pct > best_percentage:
            best_percentage = pct
            best_domain_id = domain_id
        elif pct == best_percentage and best_domain_id is not None and domain_id < best_domain_id:
            best_domain_id = domain_id

    return best_domain_id


def recommend_rule_based_with_explanation(
    per_domain_scores: DomainScores,
    domain_names: Dict[int, str],
) -> Dict[str, Any]:
    """
    Primary recommendation + ranked domains (up to tested domains) + human-readable explanation.
    """
    recommended_id = recommend_one_domain(per_domain_scores)

    ranked: List[Dict[str, Any]] = []
    for domain_id, (score, total) in per_domain_scores.items():
        if total <= 0:
            continue
        pct = round((score / total) * 100, 1)
        ranked.append(
            {
                'domain_id': domain_id,
                'domain_name': domain_names.get(domain_id, f'Domain {domain_id}'),
                'score': score,
                'total_points': total,
                'percentage': pct,
            }
        )
    ranked.sort(key=lambda x: (-x['percentage'], x['domain_id']))

    top_k = ranked[:3]

    if recommended_id is None:
        explanation = (
            'No domain recommendation: there were no scored domains in this submission.'
        )
    else:
        rec_name = domain_names.get(recommended_id, f'Domain {recommended_id}')
        rec_entry = next((r for r in ranked if r['domain_id'] == recommended_id), None)
        top_pct = rec_entry['percentage'] if rec_entry else 0.0
        ties = [r for r in ranked if r['percentage'] == top_pct]
        if len(ties) == 1:
            explanation = (
                f'Recommended {rec_name}: strongest performance among your tested domains '
                f'({top_pct}% of points earned vs available in that domain).'
            )
        else:
            others = [t['domain_name'] for t in ties if t['domain_id'] != recommended_id]
            explanation = (
                f'Recommended {rec_name}: tied at {top_pct}% with {", ".join(others)}. '
                f'Stable tie-break: lowest domain id.'
            )

    return {
        'recommended_domain_id': recommended_id,
        'ranked_domains': top_k,
        'explanation': explanation,
        'method': 'rule_based',
    }
