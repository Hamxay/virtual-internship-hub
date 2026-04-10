"""
Generate realistic project history for students listed in a data file (CSV, JSON, or Python literal list).

Default file locations (first match wins):
  - projects/data/student_data (no extension)
  - <BASE_DIR>/student_data(.csv|.json)
"""
from __future__ import annotations

import ast
import csv
import json
import random
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Domain
from assessments.models import StudentAssessmentAttempt
from projects.models import (
    ProjectSubmission,
    ProjectTemplate,
    StudentProgressSnapshot,
    StudentProjectAssignment,
    SubmissionEvaluation,
)

User = get_user_model()


def _find_student_data_file(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            raise FileNotFoundError(f"student_data path not found: {p}")
        return p.resolve()

    base = Path(settings.BASE_DIR).resolve()
    here = Path(__file__).resolve()
    projects_dir = here.parents[2]  # .../projects

    candidates = [
        projects_dir / "data" / "student_data",
        projects_dir / "data" / "student_data.csv",
        projects_dir / "data" / "student_data.json",
        base / "student_data",
        base / "student_data.csv",
        base / "student_data.json",
        base / "projects" / "data" / "student_data",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Could not find student_data file. Tried: " + ", ".join(str(c) for c in candidates)
    )


def _normalize_row_keys(row: dict) -> dict[str, str]:
    """Map common header variants to name, email, password."""
    out = {}
    for k, v in row.items():
        if k is None:
            continue
        key = str(k).strip().lower().replace(" ", "_")
        val = (v or "").strip() if isinstance(v, str) else v
        if val is None:
            val = ""
        if not isinstance(val, str):
            val = str(val)
        out[key] = val.strip()
    name = (
        out.get("name")
        or out.get("full_name")
        or out.get("username")
        or out.get("login")
        or ""
    )
    email = out.get("email") or out.get("e-mail") or ""
    password = out.get("password") or out.get("pass") or ""
    return {"name": name, "email": email, "password": password}


def _parse_student_data(path: Path) -> list[dict[str, str]]:
    raw = path.read_text(encoding="utf-8").strip()
    suffix = path.suffix.lower()

    if suffix == ".json" or (raw.startswith("[") and raw.endswith("]")):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = ast.literal_eval(raw)
        if not isinstance(data, list):
            raise ValueError("JSON / list root must be an array of objects")
        rows = []
        for item in data:
            if not isinstance(item, dict):
                continue
            rows.append(_normalize_row_keys({str(k): v for k, v in item.items()}))
        return rows

    if suffix == ".py":
        data = ast.literal_eval(raw)
        if not isinstance(data, list):
            raise ValueError("Python student_data must be a list of dicts")
        rows = []
        for item in data:
            if isinstance(item, dict):
                rows.append(_normalize_row_keys({str(k): v for k, v in item.items()}))
        return rows

    # CSV (default / no extension)
    reader = csv.DictReader(raw.splitlines())
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    rows = []
    for row in reader:
        rows.append(_normalize_row_keys(row))
    return rows


def _username_from_row(name: str, email: str, used: set[str]) -> str:
    base = (name or "").strip() or (email.split("@")[0] if email else "student")
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", base).strip("_")[:40] or "student"
    candidate = base[:150]
    n = 0
    while candidate in used or User.objects.filter(username=candidate).exists():
        n += 1
        suffix = f"_{n}"
        candidate = (base[: (150 - len(suffix))] + suffix)[:150]
    used.add(candidate)
    return candidate


def _split_display_name(name: str) -> tuple[str, str]:
    name = (name or "").strip()
    if not name:
        return "Student", ""
    parts = re.split(r"[\s_]+", name, maxsplit=1)
    if len(parts) == 1:
        return parts[0][:100], ""
    return parts[0][:100], parts[1][:100]


def _pick_target_domain_subset(all_domains: list[Domain], rng: random.Random) -> list[Domain]:
    """
    Random 2 or 3 domains (when DB has enough), matching product rules and attempt vs profile checks.
    """
    n = len(all_domains)
    if n <= 1:
        return list(all_domains)
    if n == 2:
        return list(all_domains)
    size = rng.choice([2, 3])
    return rng.sample(all_domains, size)


def _random_domain_weights_uniform(targets: list[Domain], rng: random.Random) -> dict[str, float]:
    """Positive random shards normalized to ~100% across ``targets`` (no fixed primary bias)."""
    if not targets:
        return {}
    if len(targets) == 1:
        return {str(targets[0].pk): 100.0}
    shards = [rng.random() for _ in targets]
    s = sum(shards) or 1.0
    weights: dict[str, float] = {}
    acc = 0.0
    for d, w in zip(targets, shards):
        pct = round(100.0 * (w / s), 2)
        weights[str(d.pk)] = pct
        acc += pct
    drift = round(100.0 - acc, 2)
    last_id = str(targets[-1].pk)
    weights[last_id] = round(weights[last_id] + drift, 2)
    return weights


def _primary_from_weights(targets: list[Domain], weights: dict[str, float]) -> Domain:
    """Strongest domain by weight; ties → lower id for stability."""
    return max(targets, key=lambda d: (weights.get(str(d.pk), 0.0), -float(d.pk)))


def _weighted_domain_profile_text(targets: list[Domain], weights: dict[str, float]) -> str:
    """
    Human-readable line for StudentDashboard (matches sklearn_domain_classifier style).
    """
    id_to_name = {d.pk: d.name for d in targets}
    entries: list[tuple[int, float, str]] = []
    for did_s, w in weights.items():
        did = int(did_s)
        name = id_to_name.get(did, f"Domain {did}")
        entries.append((did, float(w), name))
    entries.sort(key=lambda e: (-e[1], e[0]))
    parts = [f"{round(w):.0f}% {name}" for _, w, name in entries if w >= 1.0]
    if not parts and entries:
        _, w, name = entries[0]
        parts = [f"{round(w):.0f}% {name}"]
    return ", ".join(parts)


def _seed_passed_assessment_attempt(
    user,
    primary: Domain,
    targets: list[Domain],
    weights: dict[str, float],
    rng: random.Random,
) -> StudentAssessmentAttempt:
    """
    Passed composed attempt (≥70%) with test_domains matching profile targets so the
    student dashboard does not prompt to take the assessment.
    """
    total_points = 100
    score = int(round(rng.uniform(70.0, 100.0)))
    id_to_name = {d.pk: d.name for d in targets}
    weighted_profile = [
        {
            "domain_id": int(did),
            "domain_name": id_to_name.get(int(did), f"Domain {did}"),
            "weight_percent": float(w),
        }
        for did, w in weights.items()
    ]
    profile_text = _weighted_domain_profile_text(targets, weights)
    attempt = StudentAssessmentAttempt.objects.create(
        user=user,
        score=score,
        total_points=total_points,
        answers=[],
        recommendation_meta={
            "weighted_domain_profile": weighted_profile,
            "weighted_domain_profile_text": profile_text,
            "method": "seeded_generate_student_history",
        },
    )
    attempt.test_domains.set(targets)
    attempt.recommended_domains.set([primary])
    return attempt


def _dedupe_tags(tag_lists: list) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lst in tag_lists:
        if not isinstance(lst, list):
            continue
        for t in lst:
            s = str(t).strip()
            if not s:
                continue
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
    return out


class Command(BaseCommand):
    help = (
        "Load students from student_data (CSV/JSON/list), replace existing non-superuser accounts "
        "with those emails, then generate completed assignments, submissions, evaluations, and snapshots."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Path to student_data file (CSV, JSON, or .py list). Default: auto-discover.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = _find_student_data_file(options.get("file"))
        self.stdout.write(self.style.NOTICE(f"Using student data file: {path}"))

        rows = _parse_student_data(path)
        rows = [r for r in rows if r.get("email") and r.get("password")]
        if not rows:
            self.stdout.write(self.style.ERROR("No valid rows (need email + password)."))
            return

        emails = [r["email"].lower() for r in rows]
        deleted_qs = User.objects.filter(email__in=emails).exclude(is_superuser=True)
        deleted_n, _ = deleted_qs.delete()
        if deleted_n:
            self.stdout.write(self.style.WARNING(f"Deleted {deleted_n} related rows for {len(emails)} matching emails (non-superusers)."))

        all_domains = list(Domain.objects.all().order_by("id"))
        if not all_domains:
            self.stdout.write(self.style.ERROR("No Domain rows in DB; load domains first."))
            return

        templates_by_domain: dict[int, list[ProjectTemplate]] = {}
        for d in all_domains:
            qs = list(
                ProjectTemplate.objects.filter(domain_id=d.pk, active=True).only("id", "domain_id", "tags")
            )
            templates_by_domain[d.pk] = qs

        used_usernames: set[str] = set()
        rng = random.Random()

        for i, row in enumerate(rows, start=1):
            name = row["name"]
            email = row["email"].strip()
            password = row["password"]
            username = _username_from_row(name, email, used_usernames)
            first, last = _split_display_name(name)

            user = User.objects.create_user(
                email=email,
                username=username,
                password=password,
                role="STUDENT",
                is_email_verified=True,
            )
            if hasattr(user, "student_profile"):
                user.student_profile.first_name = first or username[:100]
                user.student_profile.last_name = last
                user.student_profile.save(update_fields=["first_name", "last_name"])

            targets = _pick_target_domain_subset(all_domains, rng)
            weights = _random_domain_weights_uniform(targets, rng)
            primary = _primary_from_weights(targets, weights)
            if hasattr(user, "student_profile"):
                user.student_profile.target_domains.set(targets)

            snapshot, _ = StudentProgressSnapshot.objects.get_or_create(student=user)
            snapshot.strongest_domain = primary
            snapshot.domain_weights = weights
            snapshot.completed_projects = 0
            snapshot.average_score = 0.0
            snapshot.current_complexity_band = "BEGINNER"
            snapshot.metadata = {}
            snapshot.save()

            pool = templates_by_domain.get(primary.pk) or []
            chosen: list[ProjectTemplate] = []
            if len(pool) < 1:
                self.stdout.write(
                    self.style.WARNING(
                        f"[{i}/{len(rows)}] {email}: no templates for domain {primary.name}; "
                        "skipping assignments (assessment still seeded)."
                    )
                )
            else:
                n_pick = min(len(pool), rng.randint(2, 6))
                chosen = rng.sample(pool, n_pick)

            scores: list[float] = []
            all_tags: list = []

            for tpl in chosen:
                overall = round(rng.uniform(0.0, 100.0), 2)
                correctness = round(rng.uniform(0.0, 100.0), 2)
                originality = round(rng.uniform(0.0, 100.0), 2)
                grammar = round(rng.uniform(0.0, 100.0), 2)
                design = round(rng.uniform(0.0, 100.0), 2)
                scores.append(overall)

                if overall >= 78.0:
                    decision = "ACCEPTED"
                    feedback_summary = f"Accepted (seeded). Overall {overall:.1f}."
                elif overall >= 45.0:
                    decision = "REVISE_AND_RESUBMIT"
                    feedback_summary = f"Revise and resubmit (seeded). Overall {overall:.1f}."
                else:
                    decision = "NEEDS_MENTOR_REVIEW"
                    feedback_summary = f"Mentor review suggested (seeded). Overall {overall:.1f}."

                tags = tpl.tags if isinstance(tpl.tags, list) else []
                all_tags.append(tags)

                assignment = StudentProjectAssignment.objects.create(
                    student=user,
                    project_template=tpl,
                    status="COMPLETED",
                    recommended_by="SEED",
                    recommendation_reason="Generated by generate_student_history",
                    latest_evaluation_score=overall,
                    latest_feedback_summary=feedback_summary,
                    completed_at=timezone.now(),
                )
                submission = ProjectSubmission.objects.create(
                    assignment=assignment,
                    version=1,
                    submission_text=f"Seeded submission for {tpl.title}.",
                    status="EVALUATED",
                )
                SubmissionEvaluation.objects.create(
                    submission=submission,
                    overall_score=overall,
                    correctness_score=correctness,
                    originality_score=originality,
                    grammar_score=grammar,
                    design_quality_score=design,
                    decision=decision,
                    feedback_summary=feedback_summary,
                    rubric_scores={},
                    strengths=["Seeded completion"],
                    improvements=[],
                    flags=[],
                    evaluation_payload={"seeded": True},
                )

            avg = round(sum(scores) / len(scores), 2) if scores else 0.0
            completed_n = len(scores)
            if completed_n >= 4 and avg >= 85:
                band = "ADVANCED"
            elif completed_n >= 2 and avg >= 70:
                band = "INTERMEDIATE"
            else:
                band = "BEGINNER"

            assignments = list(
                user.project_assignments.select_related("project_template").filter(status="COMPLETED")
            )
            meta_base = StudentProgressSnapshot.build_metadata(assignments)
            successful_tags = _dedupe_tags(all_tags)

            snapshot.completed_projects = completed_n
            snapshot.average_score = avg
            snapshot.current_complexity_band = band
            snapshot.metadata = {
                **meta_base,
                "successful_tags": successful_tags,
                "seeded_by_command": True,
            }
            snapshot.save()

            _seed_passed_assessment_attempt(user, primary, targets, weights, rng)

            self.stdout.write(
                self.style.SUCCESS(
                    f"[{i}/{len(rows)}] {email} → user {username}, {completed_n} completed, avg {avg}, "
                    f"primary domain {primary.name}, {len(successful_tags)} successful_tags, "
                    "passed assessment attempt"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Created/updated {len(rows)} students."))
