from rest_framework import serializers

from accounts.models import Domain, User
from accounts.serializers import DomainSerializer
from .models import (
    EvaluationRubric,
    ProjectInstruction,
    ProjectSubmission,
    ProjectTemplate,
    StudentProgressSnapshot,
    StudentProjectAssignment,
    SubmissionEvaluation,
)


DEFAULT_RUBRIC_CRITERIA = [
    {'key': 'correctness', 'label': 'Correctness', 'description': 'Meets the task requirements.', 'weight': 40},
    {'key': 'originality', 'label': 'Originality', 'description': 'Shows original work and low similarity.', 'weight': 25},
    {'key': 'communication', 'label': 'Communication', 'description': 'Explains work clearly and professionally.', 'weight': 15},
    {'key': 'quality', 'label': 'Quality', 'description': 'Quality of solution, structure, and completeness.', 'weight': 20},
]


class ProjectInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInstruction
        fields = (
            'overview',
            'steps',
            'deliverables',
            'submission_requirements',
            'starter_resources',
            'evaluation_notes',
        )


class EvaluationRubricSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationRubric
        fields = (
            'passing_score',
            'criteria',
            'allow_auto_accept',
            'plagiarism_threshold',
            'grammar_weight',
        )

    def validate_criteria(self, value):
        items = value or DEFAULT_RUBRIC_CRITERIA
        total_weight = 0
        for item in items:
            if not isinstance(item, dict):
                raise serializers.ValidationError('Each rubric criterion must be an object.')
            if not item.get('key') or not item.get('label'):
                raise serializers.ValidationError('Each rubric criterion must include key and label.')
            weight = float(item.get('weight', 0))
            if weight < 0:
                raise serializers.ValidationError('Criterion weights must be non-negative.')
            total_weight += weight
        if total_weight <= 0:
            raise serializers.ValidationError('Rubric criteria must have a total weight above 0.')
        return items


class ProjectTemplateSerializer(serializers.ModelSerializer):
    domain = DomainSerializer(read_only=True)
    domain_id = serializers.PrimaryKeyRelatedField(
        queryset=Domain.objects.all(),
        source='domain',
        write_only=True,
    )
    instruction = ProjectInstructionSerializer(required=False)
    rubric = EvaluationRubricSerializer(required=False)

    class Meta:
        model = ProjectTemplate
        fields = (
            'id',
            'domain',
            'domain_id',
            'title',
            'slug',
            'short_description',
            'business_problem',
            'complexity',
            'submission_type',
            'estimated_hours',
            'tags',
            'prerequisite_skills',
            'expected_keywords',
            'active',
            'instruction',
            'rubric',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'slug', 'created_at', 'updated_at', 'domain')

    def create(self, validated_data):
        instruction_data = validated_data.pop('instruction', {})
        rubric_data = validated_data.pop('rubric', {})
        template = ProjectTemplate.objects.create(**validated_data)
        ProjectInstruction.objects.create(project_template=template, **instruction_data)
        rubric_payload = {'criteria': DEFAULT_RUBRIC_CRITERIA, **rubric_data}
        EvaluationRubric.objects.create(project_template=template, **rubric_payload)
        return template

    def update(self, instance, validated_data):
        instruction_data = validated_data.pop('instruction', None)
        rubric_data = validated_data.pop('rubric', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if instruction_data is not None:
            instruction, _ = ProjectInstruction.objects.get_or_create(project_template=instance)
            for attr, value in instruction_data.items():
                setattr(instruction, attr, value)
            instruction.save()

        if rubric_data is not None:
            rubric, _ = EvaluationRubric.objects.get_or_create(
                project_template=instance,
                defaults={'criteria': DEFAULT_RUBRIC_CRITERIA},
            )
            for attr, value in rubric_data.items():
                setattr(rubric, attr, value)
            if not rubric.criteria:
                rubric.criteria = DEFAULT_RUBRIC_CRITERIA
            rubric.save()

        return instance


class SubmissionEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionEvaluation
        fields = (
            'id',
            'model_name',
            'overall_score',
            'correctness_score',
            'originality_score',
            'grammar_score',
            'design_quality_score',
            'rubric_scores',
            'strengths',
            'improvements',
            'flags',
            'decision',
            'feedback_summary',
            'reviewed_at',
        )


class ProjectSubmissionSerializer(serializers.ModelSerializer):
    evaluations = SubmissionEvaluationSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectSubmission
        fields = (
            'id',
            'version',
            'repository_url',
            'artifact_url',
            'submission_text',
            'notes',
            'submitted_files',
            'metadata',
            'status',
            'submitted_at',
            'evaluations',
        )
        read_only_fields = ('id', 'version', 'metadata', 'status', 'submitted_at', 'evaluations')


class ProjectSubmissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectSubmission
        fields = (
            'repository_url',
            'artifact_url',
            'submission_text',
            'notes',
            'submitted_files',
        )

    def validate(self, attrs):
        if not attrs.get('repository_url') and not attrs.get('artifact_url') and not attrs.get('submission_text'):
            raise serializers.ValidationError(
                'Provide at least one of repository URL, artifact URL, or submission text.'
            )
        return attrs


class StudentProjectAssignmentSerializer(serializers.ModelSerializer):
    project_template = ProjectTemplateSerializer(read_only=True)
    latest_submission = serializers.SerializerMethodField()

    class Meta:
        model = StudentProjectAssignment
        fields = (
            'id',
            'project_template',
            'status',
            'recommended_by',
            'recommendation_score',
            'recommendation_reason',
            'assigned_at',
            'accepted_at',
            'due_date',
            'completed_at',
            'attempt_number',
            'latest_evaluation_score',
            'latest_feedback_summary',
            'latest_submission',
        )

    def get_latest_submission(self, obj):
        latest = obj.latest_submission
        return ProjectSubmissionSerializer(latest).data if latest else None


class AdminAssignProjectSerializer(serializers.Serializer):
    student_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='STUDENT'),
        source='student',
    )
    project_template_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectTemplate.objects.filter(active=True),
        source='project_template',
    )
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    recommendation_reason = serializers.CharField(required=False, allow_blank=True)


class StudentProgressSnapshotSerializer(serializers.ModelSerializer):
    strongest_domain = DomainSerializer(read_only=True)

    class Meta:
        model = StudentProgressSnapshot
        fields = (
            'completed_projects',
            'average_score',
            'current_complexity_band',
            'strongest_domain',
            'domain_weights',
            'last_recommended_at',
            'metadata',
            'updated_at',
        )
