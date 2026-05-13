"""Admin analytics builders: domain score grids, cohort trends, audit CSV."""
import csv
from collections import defaultdict
from io import StringIO

from django.db.models import Prefetch

from accounts.models import Domain, StudentProfile, User
from assessments.models import StudentAssessmentAttempt
from projects.models import (
    ProjectSubmission,
    StudentProjectAssignment,
    SubmissionEvaluation,
)

PASSING_ASSESSMENT_PCT = 70.0


def _submission_mean_overall_score(submission):
    evaluations = list(submission.evaluations.all())
    if not evaluations:
        return None
    return sum(e.overall_score for e in evaluations) / len(evaluations)


def get_official_domain_names():
    """Ordered list of all catalog Domain names (e.g. 31 official domains)."""
    return list(Domain.objects.order_by('name').values_list('name', flat=True))


def get_student_domain_scores():
    """
    One object per student: scores keyed by official Domain.name only (from project template FK).
    Domains with no completed scored work in that domain are JSON null (not 0).
    overall_average is the mean of only non-null domain scores (any domain), or null if none.

    Also includes chosen_domains (sorted official domain names from the student's profile target_domains)
    and chosen_domains_average (mean of scores in those chosen domains only, among domains with data).
    """
    official = get_official_domain_names()
    official_set = set(official)
    students = list(User.objects.filter(role='STUDENT').order_by('id'))
    if not students:
        return []

    student_ids = [s.id for s in students]

    chosen_by_student = {}
    profiles = (
        StudentProfile.objects.filter(user_id__in=student_ids)
        .prefetch_related('target_domains')
    )
    for prof in profiles:
        chosen_by_student[prof.user_id] = sorted(
            d.name for d in prof.target_domains.all() if d.name in official_set
        )

    submissions = (
        ProjectSubmission.objects.filter(
            assignment__status='COMPLETED',
            assignment__student_id__in=student_ids,
        )
        .select_related(
            'assignment__student',
            'assignment__project_template__domain',
        )
        .prefetch_related(
            Prefetch('evaluations', queryset=SubmissionEvaluation.objects.all()),
        )
    )

    # student_id -> domain_name -> list of submission mean scores
    scores_by_student_domain = defaultdict(lambda: defaultdict(list))
    timeline_scores_by_student = defaultdict(list)

    for sub in submissions:
        template = sub.assignment.project_template
        if not template.domain_id:
            continue
        domain_name = template.domain.name
        if domain_name not in official_set:
            continue
        sid = sub.assignment.student_id
        score = _submission_mean_overall_score(sub)
        if score is None:
            continue
        scores_by_student_domain[sid][domain_name].append(score)
        timeline_scores_by_student[sid].append((sub.assignment.completed_at, sub.id, score))

    matrix_avg = {}
    for sid, doms in scores_by_student_domain.items():
        matrix_avg[sid] = {}
        for d_name, vals in doms.items():
            matrix_avg[sid][d_name] = sum(vals) / len(vals)

    out = []
    for st in students:
        row = {'username': st.username, 'student_id': st.id}
        active_vals = []
        for d_name in official:
            if st.id in matrix_avg and d_name in matrix_avg[st.id]:
                v = round(matrix_avg[st.id][d_name], 2)
                row[d_name] = v
                active_vals.append(v)
            else:
                row[d_name] = None
        chosen = chosen_by_student.get(st.id, [])
        row['chosen_domains'] = chosen
        chosen_scores = [row[d] for d in chosen if row.get(d) is not None]
        if chosen_scores:
            row['chosen_domains_average'] = round(
                sum(chosen_scores) / len(chosen_scores),
                2,
            )
        else:
            row['chosen_domains_average'] = None

        if active_vals:
            row['overall_average'] = round(sum(active_vals) / len(active_vals), 2)
            timeline = sorted(timeline_scores_by_student.get(st.id, []), key=lambda t: (t[0], t[1]))
            row['growth_velocity'] = (
                round(timeline[-1][2] - timeline[0][2], 2) if len(timeline) >= 2 else None
            )
        else:
            row['overall_average'] = None
            row['growth_velocity'] = None
        out.append(row)
    return out


def get_cohort_growth_analytics(max_steps=5):
    """
    Domain-level growth curves and velocity.
    Returns:
      - trends: {domain_name: [avg_step1..avg_stepN]}
      - domain_kpis: {domain_name: {"cohort_growth_velocity": float|None}}
    """
    assignments = (
        StudentProjectAssignment.objects.filter(
            status='COMPLETED',
            project_template__domain__isnull=False,
        )
        .select_related('student', 'project_template__domain')
        .order_by('student_id', 'completed_at', 'id')
        .prefetch_related(
            Prefetch(
                'submissions',
                queryset=ProjectSubmission.objects.prefetch_related(
                    Prefetch('evaluations', queryset=SubmissionEvaluation.objects.all()),
                ),
            ),
        )
    )

    student_domain_scores = defaultdict(list)
    for asn in assignments:
        vals = []
        for sub in asn.submissions.all():
            m = _submission_mean_overall_score(sub)
            if m is not None:
                vals.append(m)
        if not vals:
            continue
        domain_name = asn.project_template.domain.name
        mean_for_assignment = sum(vals) / len(vals)
        student_domain_scores[(asn.student_id, domain_name)].append(mean_for_assignment)

    by_domain_step_scores = defaultdict(lambda: defaultdict(list))
    for (_, domain_name), seq_scores in student_domain_scores.items():
        for idx, score in enumerate(seq_scores[:max_steps], start=1):
            by_domain_step_scores[domain_name][idx].append(score)

    trends = {}
    domain_kpis = {}
    for domain_name, steps in by_domain_step_scores.items():
        points = []
        for idx in range(1, max_steps + 1):
            vals = steps.get(idx, [])
            if vals:
                points.append(round(sum(vals) / len(vals), 2))
            else:
                points.append(None)
        trends[domain_name] = points

        first = points[0]
        last = points[-1]
        velocity = round(last - first, 2) if first is not None and last is not None else None
        domain_kpis[domain_name] = {
            'cohort_growth_velocity': velocity,
        }

    return trends, domain_kpis


def _student_baseline_pct(student_id):
    attempts = (
        StudentAssessmentAttempt.objects.filter(user_id=student_id)
        .order_by('submitted_at')
    )
    for att in attempts:
        if att.total_points and att.total_points > 0:
            pct = 100.0 * att.score / att.total_points
            if pct >= PASSING_ASSESSMENT_PCT:
                return pct
    return None


def _student_execution_avg(student_id):
    submissions = (
        ProjectSubmission.objects.filter(
            assignment__status='COMPLETED',
            assignment__student_id=student_id,
        ).prefetch_related(
            Prefetch('evaluations', queryset=SubmissionEvaluation.objects.all()),
        )
    )
    scores = []
    for sub in submissions:
        s = _submission_mean_overall_score(sub)
        if s is not None:
            scores.append(s)
    if not scores:
        return None
    return sum(scores) / len(scores)


def _ordered_completed_assignment_scores(student_id):
    """
    List of mean submission scores per assignment, in order of completion.
    """
    assignments = (
        StudentProjectAssignment.objects.filter(
            student_id=student_id,
            status='COMPLETED',
        )
        .order_by('completed_at', 'id')
        .prefetch_related(
            Prefetch(
                'submissions',
                queryset=ProjectSubmission.objects.prefetch_related(
                    Prefetch('evaluations', queryset=SubmissionEvaluation.objects.all()),
                ),
            ),
        )
    )
    per_assignment = []
    for asn in assignments:
        vals = []
        for sub in asn.submissions.all():
            s = _submission_mean_overall_score(sub)
            if s is not None:
                vals.append(s)
        if vals:
            per_assignment.append(sum(vals) / len(vals))
    return per_assignment


def get_platform_kpis():
    """Headline counts for the admin analytics dashboard."""
    return {
        'total_students': User.objects.filter(role='STUDENT').count(),
        'total_mentors': User.objects.filter(role='MENTOR').count(),
        'total_projects': StudentProjectAssignment.objects.filter(status='COMPLETED').count(),
    }


def build_audit_csv_text():
    """CSV rows: one line per submission evaluation (scores + mentor state)."""
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            'Date',
            'Student Username',
            'Project Title',
            'Domain',
            'AI Score',
            'Mentor Status',
        ]
    )
    evaluations = (
        SubmissionEvaluation.objects.select_related(
            'submission__assignment__student',
            'submission__assignment__project_template',
            'submission__assignment__project_template__domain',
        )
        .order_by('-reviewed_at')
        .iterator(chunk_size=500)
    )
    for ev in evaluations:
        sub = ev.submission
        asn = sub.assignment
        student = asn.student
        template = asn.project_template
        domain_name = template.domain.name if template.domain_id else ''
        reviewed = ev.reviewed_at.strftime('%Y-%m-%d %H:%M') if ev.reviewed_at else ''
        if ev.is_human_reviewed:
            status = 'Mentor reviewed'
        elif ev.decision == 'NEEDS_MENTOR_REVIEW':
            status = 'Needs mentor review'
        else:
            status = ev.get_decision_display()
        writer.writerow(
            [
                reviewed,
                student.username if student else '',
                template.title if template else '',
                domain_name,
                f'{ev.overall_score:.2f}',
                status,
            ]
        )
    return buf.getvalue()


def calculate_student_personal_progress(user):
    """
    Same signals as platform skill improvement, scoped to one student (request.user).
    """
    sid = user.id
    baseline = _student_baseline_pct(sid)
    execution = _student_execution_avg(sid)

    skill_delta_percent = 0
    if baseline is not None and execution is not None:
        if baseline > 0:
            skill_delta_percent = int(round(100.0 * (execution - baseline) / baseline))
        else:
            skill_delta_percent = 0

    ordered = _ordered_completed_assignment_scores(sid)
    time_series = [
        round(baseline, 2) if baseline is not None else None,
        round(ordered[0], 2) if len(ordered) >= 1 else None,
        round(ordered[1], 2) if len(ordered) >= 2 else None,
    ]

    return {
        'baseline_score': round(baseline, 2) if baseline is not None else None,
        'project_average': round(execution, 2) if execution is not None else None,
        'skill_delta_percent': skill_delta_percent,
        'time_series': time_series,
    }


def get_mentor_cohort_summary(mentor_user):
    """
    Aggregate scores for submissions where this mentor completed the human review
    (FCFS among mentors in matching domain; see SubmissionEvaluation.reviewed_by).
    """
    submissions = (
        ProjectSubmission.objects.filter(
            evaluations__reviewed_by=mentor_user,
            evaluations__is_human_reviewed=True,
        )
        .distinct()
        .select_related('assignment__student')
        .prefetch_related(
            Prefetch('evaluations', queryset=SubmissionEvaluation.objects.all()),
        )
    )

    scores_by_student = defaultdict(list)
    for sub in submissions:
        m = _submission_mean_overall_score(sub)
        if m is None:
            continue
        scores_by_student[sub.assignment.student_id].append(m)

    if not scores_by_student:
        return {
            'cohort_avg_score': 0.0,
            'at_risk_count': 0,
            'top_performers': [],
        }

    student_avgs = []
    for sid, vals in scores_by_student.items():
        student_avgs.append((sid, sum(vals) / len(vals)))

    cohort_avg_score = round(
        sum(a for _, a in student_avgs) / len(student_avgs),
        2,
    )
    at_risk_count = sum(1 for _, a in student_avgs if a < 70.0)

    user_map = dict(
        User.objects.filter(id__in=[t[0] for t in student_avgs]).values_list(
            'id', 'username'
        )
    )
    top = sorted(student_avgs, key=lambda x: -x[1])[:3]
    top_performers = [
        {
            'student_id': sid,
            'username': user_map.get(sid),
            'average_score': round(avg, 2),
        }
        for sid, avg in top
    ]

    return {
        'cohort_avg_score': cohort_avg_score,
        'at_risk_count': at_risk_count,
        'top_performers': top_performers,
    }
