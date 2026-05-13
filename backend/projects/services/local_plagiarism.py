from __future__ import annotations

from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from projects.models import ProjectSubmission


def _normalize(text: str) -> str:
    return ' '.join(str(text or '').split()).strip()


def _candidate_texts(submission: ProjectSubmission, limit: int = 300) -> list[str]:
    rows = (
        ProjectSubmission.objects.filter(
            assignment__project_template_id=submission.assignment.project_template_id,
            status__in=['EVALUATED', 'FLAGGED', 'SUBMITTED'],
        )
        .exclude(pk=submission.pk)
        .exclude(assignment__student_id=submission.assignment.student_id)
        .only('submission_text', 'notes')
        .order_by('-submitted_at', '-id')[:limit]
    )

    out: list[str] = []
    for row in rows:
        text = _normalize(f'{row.submission_text or ""}\n{row.notes or ""}')
        if text:
            out.append(text)
    return out


def _max_cosine_similarity_percent(target_text: str, corpus_texts: Iterable[str]) -> float | None:
    target = _normalize(target_text)
    corpus = [target, *[t for t in corpus_texts if _normalize(t)]]
    if len(corpus) <= 1:
        return None

    vectorizer = TfidfVectorizer(lowercase=True, stop_words='english', ngram_range=(1, 2))
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return None
    sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    if sims.size == 0:
        return None

    score = float(sims.max()) * 100.0
    return round(max(0.0, min(100.0, score)), 2)


def compute_local_similarity_percent(submission: ProjectSubmission, extracted_text: str) -> float | None:
    candidates = _candidate_texts(submission)
    return _max_cosine_similarity_percent(extracted_text, candidates)
