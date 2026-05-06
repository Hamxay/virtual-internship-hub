from django.contrib.auth import get_user_model
from rest_framework import serializers

from projects.models import ProjectSubmission, StudentProjectAssignment
from projects.serializers import ProjectTemplateSerializer, SubmissionEvaluationSerializer

User = get_user_model()


class MentorStudentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')


class MentorAssignmentSummarySerializer(serializers.ModelSerializer):
    """Assignment context for the review queue (no nested latest_submission)."""

    project_template = ProjectTemplateSerializer(read_only=True)
    student = MentorStudentBriefSerializer(read_only=True)

    class Meta:
        model = StudentProjectAssignment
        fields = (
            'id',
            'status',
            'student',
            'project_template',
            'latest_evaluation_score',
            'latest_feedback_summary',
            'assigned_at',
        )


class MentorQueueSubmissionSerializer(serializers.ModelSerializer):
    evaluations = SubmissionEvaluationSerializer(many=True, read_only=True)
    assignment = MentorAssignmentSummarySerializer(read_only=True)

    class Meta:
        model = ProjectSubmission
        fields = (
            'id',
            'version',
            'uploaded_file',
            'submission_text',
            'notes',
            'submitted_files',
            'metadata',
            'status',
            'submitted_at',
            'evaluations',
            'assignment',
        )


class MentorReviewActionSerializer(serializers.Serializer):
    submission_id = serializers.IntegerField()
    mentor_feedback = serializers.CharField(allow_blank=True, required=False, default='')
    approved = serializers.BooleanField()
