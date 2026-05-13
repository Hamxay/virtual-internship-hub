from __future__ import annotations

import random
from datetime import timedelta

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

TARGET_DOMAIN_NAMES = (
    'Java Programming',
    'Communication & Soft Skills',
    'PHP Development',
)

FIRST_NAMES = [
    'Ali', 'Ayesha', 'Bilal', 'Fatima', 'Hassan', 'Hina', 'Usman', 'Sara', 'Zain', 'Maryam',
    'Hamza', 'Iqra', 'Talha', 'Noor', 'Danish', 'Maham', 'Saad', 'Komal', 'Owais', 'Nimra',
]
LAST_NAMES = [
    'Khan', 'Ahmed', 'Malik', 'Raza', 'Iqbal', 'Siddiqui', 'Javed', 'Nawaz', 'Farooq', 'Aslam',
    'Qureshi', 'Sheikh', 'Butt', 'Shah', 'Hussain', 'Latif', 'Mirza', 'Tariq', 'Saleem', 'Anwar',
]


def _subsidiary_scores_from_overall(overall: float, rng: random.Random) -> tuple[float, float, float, float]:
    def clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    return (
        clamp(overall + rng.uniform(-10.0, 10.0)),
        clamp(overall + rng.uniform(-10.0, 10.0)),
        clamp(overall + rng.uniform(-10.0, 10.0)),
        clamp(overall + rng.uniform(-10.0, 10.0)),
    )


def _decision_and_feedback(overall: float) -> tuple[str, str]:
    if overall >= 78.0:
        return 'ACCEPTED', f'Accepted (seeded). Overall {overall:.1f}.'
    if overall >= 45.0:
        return 'REVISE_AND_RESUBMIT', f'Revise and resubmit (seeded). Overall {overall:.1f}.'
    return 'NEEDS_MENTOR_REVIEW', f'Mentor review suggested (seeded). Overall {overall:.1f}.'


def _dedupe_tags(tag_lists: list) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tag_list in tag_lists:
        if not isinstance(tag_list, list):
            continue
        for tag in tag_list:
            label = str(tag).strip()
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
    return out


def _random_domain_weights_uniform(targets: list[Domain], rng: random.Random) -> dict[str, float]:
    if not targets:
        return {}
    shards = [rng.random() for _ in targets]
    total = sum(shards) or 1.0
    weights: dict[str, float] = {}
    acc = 0.0
    for domain, shard in zip(targets, shards):
        pct = round(100.0 * (shard / total), 2)
        weights[str(domain.pk)] = pct
        acc += pct
    drift = round(100.0 - acc, 2)
    last_id = str(targets[-1].pk)
    weights[last_id] = round(weights[last_id] + drift, 2)
    return weights


class Command(BaseCommand):
    help = (
        'Generate random students with completed history for exactly 3 domains: '
        'Java Programming, Communication & Soft Skills, PHP Development '
        '(unique templates per student).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--students',
            type=int,
            default=10,
            help='Number of random students to create (default: 10).',
        )
        parser.add_argument(
            '--projects-per-domain',
            type=int,
            default=3,
            help='Completed projects per domain per student (default: 3).',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='Student@123',
            help='Password to set for generated students (default: Student@123).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        student_count = max(10, int(options['students'] or 10))
        projects_per_domain = max(1, int(options['projects_per_domain'] or 5))
        password = str(options['password'] or 'Student@123')
        rng = random.Random()

        domains: list[Domain] = []
        missing_domains: list[str] = []
        for name in TARGET_DOMAIN_NAMES:
            domain = Domain.objects.filter(name__iexact=name).first()
            if domain is None:
                missing_domains.append(name)
            else:
                domains.append(domain)
        if missing_domains:
            self.stdout.write(
                self.style.ERROR(
                    f'Missing required domains: {", ".join(missing_domains)}'
                )
            )
            return

        templates_by_domain: dict[int, list[ProjectTemplate]] = {}
        for domain in domains:
            pool = list(
                ProjectTemplate.objects.filter(domain=domain, active=True).only(
                    'id', 'title', 'domain_id', 'tags'
                )
            )
            if len(pool) < projects_per_domain:
                self.stdout.write(
                    self.style.ERROR(
                        f'Domain "{domain.name}" has only {len(pool)} active templates; '
                        f'need at least {projects_per_domain}.'
                    )
                )
                return
            templates_by_domain[domain.id] = pool

        mentor_profiles = list(
            MentorProfile.objects.select_related('user', 'expertise_domain').filter(
                expertise_domain__isnull=False,
                user__role='MENTOR',
            )
        )
        mentors_by_domain_id: dict[int, list[User]] = {}
        for profile in mentor_profiles:
            mentors_by_domain_id.setdefault(profile.expertise_domain_id, []).append(profile.user)

        run_token = timezone.now().strftime('%Y%m%d%H%M%S')

        for index in range(1, student_count + 1):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            full_name = f'{first} {last}'
            username = f'rand_hist_{run_token}_{index}'
            email = f'{username}@seed.local'

            user = User.objects.create_user(
                email=email,
                username=username[:150],
                password=password,
                role='STUDENT',
                is_email_verified=True,
            )

            if hasattr(user, 'student_profile'):
                user.student_profile.first_name = first
                user.student_profile.last_name = last
                user.student_profile.save(update_fields=['first_name', 'last_name'])
                user.student_profile.target_domains.set(domains)

            weights = _random_domain_weights_uniform(domains, rng)
            primary = max(domains, key=lambda d: (weights.get(str(d.pk), 0.0), -float(d.pk)))

            snapshot, _ = StudentProgressSnapshot.objects.get_or_create(student=user)
            snapshot.strongest_domain = primary
            snapshot.domain_weights = weights
            snapshot.completed_projects = 0
            snapshot.average_score = 0.0
            snapshot.current_complexity_band = 'BEGINNER'
            snapshot.metadata = {}
            snapshot.save()

            scores: list[float] = []
            all_tags: list = []
            base_date = timezone.now() - timedelta(
                weeks=(len(domains) * projects_per_domain) + 2
            )

            for domain in domains:
                # random.sample picks unique templates (no repeats) within this domain.
                chosen = rng.sample(templates_by_domain[domain.id], projects_per_domain)
                trajectory = rng.choice(['IMPROVING', 'FAILING', 'STABLE'])
                if trajectory == 'IMPROVING':
                    starting_score = rng.randint(40, 55)
                    trajectory_step = rng.randint(4, 8)
                elif trajectory == 'FAILING':
                    starting_score = rng.randint(85, 95)
                    trajectory_step = rng.randint(4, 8)
                else:
                    starting_score = rng.randint(72, 86)
                    trajectory_step = 0

                for project_index, template in enumerate(chosen):
                    if trajectory == 'IMPROVING':
                        current_score = float(min(100, starting_score + (project_index * trajectory_step)))
                    elif trajectory == 'FAILING':
                        current_score = float(max(0, starting_score - (project_index * trajectory_step)))
                    else:
                        current_score = float(max(0, min(100, starting_score + rng.randint(-5, 5))))

                    overall = round(current_score, 2)
                    correctness, originality, grammar, design = _subsidiary_scores_from_overall(overall, rng)
                    decision, feedback_summary = _decision_and_feedback(overall)
                    project_date = base_date + timedelta(
                        days=(project_index * 7) + rng.randint(0, 2)
                    )

                    tags = template.tags if isinstance(template.tags, list) else []
                    all_tags.append(tags)

                    assignment = StudentProjectAssignment.objects.create(
                        student=user,
                        project_template=template,
                        status='COMPLETED',
                        recommended_by='SEED',
                        recommendation_reason='Generated by generate_random_student_history',
                        recommendation_source='CONTENT_BASED',
                        latest_evaluation_score=overall,
                        latest_feedback_summary=feedback_summary,
                    )
                    StudentProjectAssignment.objects.filter(pk=assignment.pk).update(
                        assigned_at=project_date,
                        completed_at=project_date,
                    )

                    submission = ProjectSubmission.objects.create(
                        assignment=assignment,
                        version=1,
                        submission_text=f'Seeded submission for {template.title}.',
                        status='EVALUATED',
                    )
                    ProjectSubmission.objects.filter(pk=submission.pk).update(submitted_at=project_date)

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
                        strengths=['Seeded completion'],
                        improvements=[],
                        flags=[],
                        is_human_reviewed=True,
                        reviewed_by=(
                            rng.choice(mentors_by_domain_id.get(domain.pk, []))
                            if mentors_by_domain_id.get(domain.pk)
                            else None
                        ),
                        evaluation_payload={
                            'seeded': True,
                            'seed_trajectory': trajectory,
                            'seed_command': 'generate_random_student_history',
                        },
                    )
                    SubmissionEvaluation.objects.filter(pk=evaluation.pk).update(reviewed_at=project_date)
                    scores.append(overall)

            completed_n = len(scores)
            avg = round(sum(scores) / completed_n, 2) if scores else 0.0
            if completed_n >= 4 and avg >= 85:
                band = 'ADVANCED'
            elif completed_n >= 2 and avg >= 70:
                band = 'INTERMEDIATE'
            else:
                band = 'BEGINNER'

            completed_assignments = list(
                user.project_assignments.select_related('project_template').filter(status='COMPLETED')
            )
            meta_base = StudentProgressSnapshot.build_metadata(completed_assignments)
            successful_tags = _dedupe_tags(all_tags)

            snapshot.completed_projects = completed_n
            snapshot.average_score = avg
            snapshot.current_complexity_band = band
            snapshot.metadata = {
                **meta_base,
                'successful_tags': successful_tags,
                'seeded_by_command': True,
                'seed_command': 'generate_random_student_history',
            }
            snapshot.save()

            attempt = StudentAssessmentAttempt.objects.create(
                user=user,
                score=rng.randint(70, 100),
                total_points=100,
                answers=[],
                recommendation_meta={
                    'method': 'seeded_generate_random_student_history',
                    'weighted_domain_profile': [
                        {
                            'domain_id': domain.id,
                            'domain_name': domain.name,
                            'weight_percent': float(weights.get(str(domain.id), 0.0)),
                        }
                        for domain in domains
                    ],
                },
            )
            attempt.test_domains.set(domains)
            attempt.recommended_domains.set([primary])

            self.stdout.write(
                self.style.SUCCESS(
                    f'[{index}/{student_count}] {full_name} ({email}) -> '
                    f'{completed_n} completed projects across 3 domains, avg {avg}, '
                    f'primary domain {primary.name}'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created {student_count} random students with exactly 3 domains '
                f'({", ".join(TARGET_DOMAIN_NAMES)}).'
            )
        )
