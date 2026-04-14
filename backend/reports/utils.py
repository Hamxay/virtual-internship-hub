"""
FR9 analytics: clustering and skill progression aggregates.
"""
from collections import defaultdict

import pandas as pd
from django.db.models import Prefetch
from sklearn.cluster import KMeans

from accounts.models import User  # Custom user model (is_student via role)
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


def _template_domain_keys(template):
    tags = template.tags or []
    if isinstance(tags, list) and tags:
        return [str(t) for t in tags]
    if template.domain_id:
        return [template.domain.name]
    return ['Unknown']


def get_student_clusters():
    """
    Rows = students, columns = domain labels from project template tags (or domain name).
    KMeans with 3 clusters when at least 3 students; else cluster 0 for all.
    """
    students = list(User.objects.filter(role='STUDENT').order_by('id'))
    if not students:
        return []

    student_ids = [s.id for s in students]
    submissions = (
        ProjectSubmission.objects.filter(
            assignment__status='COMPLETED',
            assignment__student_id__in=student_ids,
        )
        .select_related('assignment__student', 'assignment__project_template__domain')
        .prefetch_related(
            Prefetch('evaluations', queryset=SubmissionEvaluation.objects.all()),
        )
    )

    # student_id -> domain_key -> list of scores (one per submission contribution)
    scores_by_student_domain = defaultdict(lambda: defaultdict(list))

    for sub in submissions:
        sid = sub.assignment.student_id
        score = _submission_mean_overall_score(sub)
        if score is None:
            continue
        for key in _template_domain_keys(sub.assignment.project_template):
            scores_by_student_domain[sid][key].append(score)

    # collapse lists to averages per (student, domain)
    matrix = {}
    all_domains = set()
    for sid, domains in scores_by_student_domain.items():
        matrix[sid] = {}
        for d, vals in domains.items():
            matrix[sid][d] = sum(vals) / len(vals)
            all_domains.add(d)

    if not all_domains:
        return [
            {'username': st.username, 'cluster': 0}
            for st in students
        ]

    all_domains = sorted(all_domains)
    rows = []
    for st in students:
        row = {'username': st.username}
        for d in all_domains:
            row[d] = matrix.get(st.id, {}).get(d)
        rows.append(row)

    df = pd.DataFrame(rows).set_index('username')
    domain_cols = [c for c in df.columns if c != 'cluster']
    df[domain_cols] = df[domain_cols].fillna(0)

    feature_cols = [c for c in df.columns]
    if len(df) >= 3:
        km = KMeans(n_clusters=3, random_state=42, n_init='auto')
        df['cluster'] = km.fit_predict(df[feature_cols].values)
    else:
        df['cluster'] = 0

    out = []
    for _, series in df.reset_index().iterrows():
        rec = {'username': str(series['username']), 'cluster': int(series['cluster'])}
        for c in feature_cols:
            rec[c] = float(series[c])
        out.append(rec)
    return out


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


def calculate_skill_improvement():
    """
    Skill delta: baseline from first passing assessment vs mean project execution score.
    """
    student_ids = list(
        User.objects.filter(role='STUDENT').values_list('id', flat=True)
    )
    growth_samples = []
    baselines = []
    project1_scores = []
    project2_scores = []

    for sid in student_ids:
        baseline = _student_baseline_pct(sid)
        if baseline is not None:
            baselines.append(baseline)

        execution = _student_execution_avg(sid)
        if baseline is not None and execution is not None:
            if baseline > 0:
                growth_samples.append(100.0 * (execution - baseline) / baseline)
            else:
                growth_samples.append(0.0)

        ordered = _ordered_completed_assignment_scores(sid)
        if len(ordered) >= 1:
            project1_scores.append(ordered[0])
        if len(ordered) >= 2:
            project2_scores.append(ordered[1])

    platform_average_growth = (
        int(round(sum(growth_samples) / len(growth_samples)))
        if growth_samples
        else 0
    )

    def _avg(seq):
        return round(sum(seq) / len(seq), 2) if seq else 0.0

    time_series = [
        _avg(baselines),
        _avg(project1_scores),
        _avg(project2_scores),
    ]

    return {
        'platform_average_growth': platform_average_growth,
        'time_series': time_series,
    }


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
    Aggregate submission scores for assignments linked to this mentor.
    """
    submissions = (
        ProjectSubmission.objects.filter(assignment__mentor=mentor_user)
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
