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
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Domain, MentorProfile
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


def _find_mentor_data_file() -> Path | None:
    base = Path(settings.BASE_DIR).resolve()
    here = Path(__file__).resolve()
    projects_dir = here.parents[2]  # .../projects
    candidates = [
        projects_dir / "data" / "mentor_data.csv",
        base / "mentor_data.csv",
        base / "projects" / "data" / "mentor_data.csv",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


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
    # NOTE: extra CSV keys are preserved in `out` for downstream domain parsing.


def _normalize_row(row: dict) -> dict[str, str]:
    """
    Normalize common account fields but also keep any domain columns.
    """
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
    base = _normalize_row_keys(row)
    out.update(base)
    return out


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
            rows.append(_normalize_row({str(k): v for k, v in item.items()}))
        return rows

    if suffix == ".py":
        data = ast.literal_eval(raw)
        if not isinstance(data, list):
            raise ValueError("Python student_data must be a list of dicts")
        rows = []
        for item in data:
            if isinstance(item, dict):
                rows.append(_normalize_row({str(k): v for k, v in item.items()}))
        return rows

    # CSV (default / no extension)
    reader = csv.DictReader(raw.splitlines())
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    rows = []
    for row in reader:
        rows.append(_normalize_row(row))
    return rows


def _parse_mentor_data(path: Path) -> list[dict[str, str]]:
    raw = path.read_text(encoding="utf-8").strip()
    reader = csv.DictReader(raw.splitlines())
    if not reader.fieldnames:
        raise ValueError("mentor_data CSV has no header row")
    rows = []
    for row in reader:
        norm = _normalize_row(row)
        rows.append(norm)
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


def _extract_domains_from_student_row(row: dict, eligible_domains: list[Domain]) -> list[Domain]:
    domain_by_name = {d.name.strip().lower(): d for d in eligible_domains}
    raw_fields = [
        row.get("domain"),
        row.get("domain1"),
        row.get("domain2"),
        row.get("domain3"),
        row.get("target_domain"),
        row.get("target_domains"),
        row.get("domains"),
    ]
    tokens = []
    for field in raw_fields:
        if not field:
            continue
        text = str(field).strip()
        if not text:
            continue
        parts = re.split(r"[|,;/]+", text)
        for p in parts:
            t = p.strip()
            if t:
                tokens.append(t)
    seen = set()
    selected = []
    for token in tokens:
        d = domain_by_name.get(token.lower())
        if d is None:
            continue
        if d.id in seen:
            continue
        seen.add(d.id)
        selected.append(d)
        if len(selected) == 3:
            break
    return selected


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


def _subsidiary_scores_from_overall(overall: float, rng: random.Random) -> tuple[float, float, float, float]:
    """Keep rubric sub-scores near overall so seeded rows look coherent in reports."""

    def clamp(x: float) -> float:
        return round(max(0.0, min(100.0, x)), 2)

    jitter = lambda: rng.uniform(-10.0, 10.0)
    return (
        clamp(overall + jitter()),
        clamp(overall + jitter()),
        clamp(overall + jitter()),
        clamp(overall + jitter()),
    )


def _decision_and_feedback(overall: float) -> tuple[str, str]:
    if overall >= 78.0:
        return (
            "ACCEPTED",
            f"Accepted (seeded). Overall {overall:.1f}.",
        )
    if overall >= 45.0:
        return (
            "REVISE_AND_RESUBMIT",
            f"Revise and resubmit (seeded). Overall {overall:.1f}.",
        )
    return (
        "NEEDS_MENTOR_REVIEW",
        f"Mentor review suggested (seeded). Overall {overall:.1f}.",
    )


def _ensure_mentors(all_domains: list[Domain], rng: random.Random, stdout):
    mentor_file = _find_mentor_data_file()
    rows = []
    if mentor_file:
        rows = _parse_mentor_data(mentor_file)
        rows = [r for r in rows if r.get("email") and r.get("password")]
        stdout.write(f"Using mentor data file: {mentor_file}")
    else:
        rows = []
        for d in all_domains:
            rows.append(
                {
                    "name": f"{d.name} Mentor",
                    "email": f"mentor_{d.code.lower()}@seed.local",
                    "password": "Mentor@123",
                }
            )
        stdout.write("mentor_data.csv not found; generating one mentor per domain.")

    used_usernames: set[str] = set()
    for idx, row in enumerate(rows):
        domain = all_domains[idx % len(all_domains)]
        username = _username_from_row(row.get("name", ""), row["email"], used_usernames)
        mentor_user, _ = User.objects.update_or_create(
            email=row["email"].strip().lower(),
            defaults={
                "username": username,
                "role": "MENTOR",
                "is_email_verified": True,
            },
        )
        mentor_user.set_password(row["password"])
        mentor_user.save(update_fields=["password"])
        MentorProfile.objects.update_or_create(
            user=mentor_user,
            defaults={
                "professional_bio": "Seeded mentor profile for dashboard triage and review queue.",
                "expertise_domain": domain,
                "years_of_experience": rng.randint(3, 12),
                "is_available": True,
            },
        )


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
        _ensure_mentors(all_domains, random.Random(), self.stdout)
        mentor_profiles = list(
            MentorProfile.objects.select_related('user', 'expertise_domain').filter(
                expertise_domain__isnull=False,
                user__role='MENTOR',
            )
        )
        mentors_by_domain_id: dict[int, list] = {}
        for mp in mentor_profiles:
            mentors_by_domain_id.setdefault(mp.expertise_domain_id, []).append(mp.user)

        templates_by_domain: dict[int, list[ProjectTemplate]] = {}
        for d in all_domains:
            qs = list(
                ProjectTemplate.objects.filter(domain_id=d.pk, active=True).only("id", "domain_id", "tags")
            )
            templates_by_domain[d.pk] = qs
        eligible_domains = [d for d in all_domains if len(templates_by_domain.get(d.pk, [])) >= 5]
        if len(eligible_domains) < 2:
            self.stdout.write(
                self.style.ERROR(
                    "Need at least 2 domains with >=5 active templates each to guarantee "
                    "5 projects per assigned domain."
                )
            )
            return

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

            row_targets = _extract_domains_from_student_row(row, eligible_domains)
            if len(row_targets) >= 2:
                targets = row_targets[:3]
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"[{i}/{len(rows)}] {email}: missing/invalid domain columns; "
                        "skipping student (no random domain fallback)."
                    )
                )
                continue
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

            scores: list[float] = []
            all_tags: list = []
            for domain in targets:
                pool = templates_by_domain.get(domain.pk) or []
                chosen = rng.sample(pool, 5)
                trajectory = rng.choice(["IMPROVING", "FAILING", "STABLE"])

                if trajectory == "IMPROVING":
                    starting_score = rng.randint(40, 55)
                    trajectory_step = rng.randint(4, 8)
                elif trajectory == "FAILING":
                    starting_score = rng.randint(85, 95)
                    trajectory_step = rng.randint(4, 8)
                else:
                    starting_score = rng.randint(75, 85)
                    trajectory_step = 0

                base_date = timezone.now() - timedelta(weeks=(len(targets) * 5) + 2)

                for idx, tpl in enumerate(chosen):
                    if trajectory == "IMPROVING":
                        current_score = float(min(100, starting_score + (idx * trajectory_step)))
                    elif trajectory == "FAILING":
                        current_score = float(max(0, starting_score - (idx * trajectory_step)))
                    else:
                        current_score = float(max(0, min(100, starting_score + rng.randint(-5, 5))))

                    overall = round(current_score, 2)
                    correctness, originality, grammar, design = _subsidiary_scores_from_overall(overall, rng)
                    decision, feedback_summary = _decision_and_feedback(overall)
                    project_date = base_date + timedelta(days=(idx * 7) + rng.randint(0, 2))

                    tags = tpl.tags if isinstance(tpl.tags, list) else []
                    all_tags.append(tags)
                    is_latest_project = idx == 4
                    keep_pending_review = is_latest_project and (rng.random() < 0.30)

                    assignment_status = "SUBMITTED" if keep_pending_review else "COMPLETED"
                    assignment = StudentProjectAssignment.objects.create(
                        student=user,
                        project_template=tpl,
                        status=assignment_status,
                        recommended_by="SEED",
                        recommendation_reason="Generated by generate_student_history",
                        latest_evaluation_score=None if keep_pending_review else overall,
                        latest_feedback_summary="" if keep_pending_review else feedback_summary,
                    )
                    StudentProjectAssignment.objects.filter(pk=assignment.pk).update(
                        assigned_at=project_date,
                        completed_at=None if keep_pending_review else project_date,
                    )

                    submission = ProjectSubmission.objects.create(
                        assignment=assignment,
                        version=1,
                        submission_text=f"Seeded submission for {tpl.title}.",
                        status="SUBMITTED" if keep_pending_review else "EVALUATED",
                    )
                    ProjectSubmission.objects.filter(pk=submission.pk).update(submitted_at=project_date)

                    if keep_pending_review:
                        continue

                    scores.append(overall)
                    evaluation = SubmissionEvaluation.objects.create(
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
                        is_human_reviewed=True,
                        reviewed_by=(rng.choice(mentors_by_domain_id.get(domain.pk, [])) if mentors_by_domain_id.get(domain.pk) else None),
                        evaluation_payload={
                            "seeded": True,
                            "seed_trajectory": trajectory,
                        },
                    )
                    SubmissionEvaluation.objects.filter(pk=evaluation.pk).update(reviewed_at=project_date)

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
                    f"[{i}/{len(rows)}] {email} → user {username}, "
                    f"{len(targets) * 5} generated ({completed_n} evaluated), avg {avg}, "
                    f"primary domain {primary.name}, {len(successful_tags)} successful_tags, "
                    "passed assessment attempt"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Created/updated {len(rows)} students."))
