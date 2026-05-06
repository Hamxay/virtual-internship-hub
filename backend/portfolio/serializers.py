from rest_framework import serializers

from accounts.models import User
from projects.models import ProjectSubmission


def _best_human_reviewed_evaluation(submission):
    reviewed = [e for e in submission.evaluations.all() if e.is_human_reviewed]
    if not reviewed:
        return None
    return max(reviewed, key=lambda e: (e.overall_score or 0.0, e.reviewed_at))


class PublicStudentProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='student_profile.first_name', read_only=True)
    last_name = serializers.CharField(source='student_profile.last_name', read_only=True)
    bio = serializers.CharField(source='student_profile.bio', read_only=True, allow_null=True)
    target_domains = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'bio', 'target_domains')

    def get_target_domains(self, obj):
        sp = getattr(obj, 'student_profile', None)
        if not sp:
            return []
        return [d.name for d in sp.target_domains.all()]


class PublicProjectShowcaseSerializer(serializers.ModelSerializer):
    template_title = serializers.CharField(source='assignment.project_template.title', read_only=True)
    template_description = serializers.CharField(
        source='assignment.project_template.short_description',
        read_only=True,
    )
    template_tags = serializers.JSONField(source='assignment.project_template.tags', read_only=True)
    overall_score = serializers.SerializerMethodField()
    mentor_feedback = serializers.SerializerMethodField()

    class Meta:
        model = ProjectSubmission
        fields = (
            'id',
            'uploaded_file',
            'template_title',
            'template_description',
            'template_tags',
            'overall_score',
            'mentor_feedback',
        )

    def get_overall_score(self, obj):
        ev = _best_human_reviewed_evaluation(obj)
        return float(ev.overall_score) if ev else None

    def get_mentor_feedback(self, obj):
        ev = _best_human_reviewed_evaluation(obj)
        return ev.mentor_feedback if ev else None
