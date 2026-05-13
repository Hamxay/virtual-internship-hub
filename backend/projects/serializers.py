import json
from pathlib import Path

from rest_framework import serializers

from accounts.models import Domain, User
from accounts.serializers import DomainSerializer
from .models import (
    FILE_SUBMISSION_TYPES,
    EvaluationRubric,
    ProjectInstruction,
    ProjectSubmission,
    ProjectTemplate,
    StudentProgressSnapshot,
    StudentProjectAssignment,
    SubmissionEvaluation,
)


MAX_SUBMISSION_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_SUBMISSION_UPLOAD_SUFFIXES = frozenset({
    '.pdf', '.doc', '.docx', '.xlsx', '.xls', '.txt',
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.zip',
})

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
        criteria_items = value or DEFAULT_RUBRIC_CRITERIA
        total_weight = 0
        for item in criteria_items:
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
        return criteria_items


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
    """Surfaces model tags and plagiarism similarity % alongside stored rubric JSON."""

    extracted_tags = serializers.SerializerMethodField()
    plagiarism_similarity_percent = serializers.SerializerMethodField(
        help_text='Plagiarism similarity % from evaluation data or submission metadata.',
    )

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
            'plagiarism_similarity_percent',
            'rubric_scores',
            'strengths',
            'improvements',
            'flags',
            'decision',
            'feedback_summary',
            'reviewed_at',
            'mentor_feedback',
            'is_human_reviewed',
            'reviewed_by',
            'extracted_tags',
        )

    def get_extracted_tags(self, obj):
        rubric_scores = obj.rubric_scores if isinstance(obj.rubric_scores, dict) else {}
        raw = rubric_scores.get('extracted_tags')
        if isinstance(raw, list):
            out = [str(t).strip() for t in raw if str(t).strip()]
            if out:
                return out
        if obj.submission_id:
            meta = getattr(obj.submission, 'metadata', None) or {}
            alt = meta.get('extracted_tags')
            if not isinstance(alt, list):
                alt = meta.get('fr4_extracted_tags')
            if isinstance(alt, list):
                return [str(t).strip() for t in alt if str(t).strip()]
        return []

    def get_plagiarism_similarity_percent(self, obj):
        rubric_scores = obj.rubric_scores if isinstance(obj.rubric_scores, dict) else {}
        if obj.model_name in {'local_plagiarism_gatekeeper', 'copyleaks_plagiarism_gatekeeper'}:
            v = rubric_scores.get('similarity_percent')
            if v is not None:
                try:
                    return round(float(v), 2)
                except (TypeError, ValueError):
                    pass
        model_json = rubric_scores.get('model_json') if isinstance(rubric_scores, dict) else None
        if isinstance(model_json, dict):
            v = model_json.get('plagiarism_similarity_percent')
            if v is not None:
                try:
                    return round(float(v), 2)
                except (TypeError, ValueError):
                    pass
        v = rubric_scores.get('plagiarism_similarity_percent')
        if v is not None:
            try:
                return round(float(v), 2)
            except (TypeError, ValueError):
                pass
        if not obj.submission_id:
            return None
        meta = getattr(obj.submission, 'metadata', None) or {}
        raw = meta.get('plagiarism_similarity_percent')
        if raw in (None, ''):
            raw = meta.get('copyleaks_similarity_percent')
        if raw is None or raw == '':
            return None
        try:
            return round(float(raw), 2)
        except (TypeError, ValueError):
            return None


class ProjectSubmissionSerializer(serializers.ModelSerializer):
    evaluations = SubmissionEvaluationSerializer(many=True, read_only=True)

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
        )
        read_only_fields = (
            'id',
            'version',
            'metadata',
            'status',
            'submitted_at',
            'evaluations',
            'uploaded_file',
        )


class ProjectSubmissionCreateSerializer(serializers.ModelSerializer):
    uploaded_file = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = ProjectSubmission
        fields = (
            'uploaded_file',
            'submission_text',
            'notes',
            'submitted_files',
        )

    def validate_submitted_files(self, value):
        if value in (None, '', []):
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError('Must be a valid JSON array of strings.') from exc
            if not isinstance(parsed, list):
                raise serializers.ValidationError('Must be a JSON array.')
            return [str(x).strip() for x in parsed if str(x).strip()]
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        raise serializers.ValidationError('Invalid format.')

    def validate(self, attrs):
        assignment = self.context.get('assignment')
        if assignment is None:
            raise serializers.ValidationError('Assignment context is required.')

        template = assignment.project_template
        submission_type = template.submission_type
        uploaded_file = attrs.get('uploaded_file')
        has_upload = bool(uploaded_file)

        if not has_upload:
            if submission_type == 'CODE':
                raise serializers.ValidationError(
                    {'uploaded_file': 'Code submissions require a ZIP upload.'}
                )
            raise serializers.ValidationError(
                {'uploaded_file': 'This project type requires an uploaded file.'}
            )
        if submission_type in FILE_SUBMISSION_TYPES or submission_type == 'CODE':
            size = getattr(uploaded_file, 'size', None)
            if size is not None and size > MAX_SUBMISSION_UPLOAD_BYTES:
                raise serializers.ValidationError(
                    {'uploaded_file': f'File too large (max {MAX_SUBMISSION_UPLOAD_BYTES // (1024 * 1024)} MB).'}
                )
            name = getattr(uploaded_file, 'name', '') or ''
            suffix = Path(name).suffix.lower()
            if submission_type == 'CODE' and suffix != '.zip':
                raise serializers.ValidationError(
                    {'uploaded_file': 'Code submissions must be a .zip file.'}
                )
            if suffix not in ALLOWED_SUBMISSION_UPLOAD_SUFFIXES:
                raise serializers.ValidationError(
                    {
                        'uploaded_file': (
                            f'Unsupported type ({suffix or "unknown"}). '
                            f'Allowed: {", ".join(sorted(ALLOWED_SUBMISSION_UPLOAD_SUFFIXES))}'
                        )
                    }
                )
        return attrs

    def create(self, validated_data):
        assignment = self.context['assignment']
        version = self.context.get('version', 1)
        validated_data.setdefault('submitted_files', [])
        instance = ProjectSubmission(assignment=assignment, version=version, **validated_data)
        instance.full_clean()
        instance.save()
        return instance


class StudentProjectAssignmentSerializer(serializers.ModelSerializer):
    project_template = ProjectTemplateSerializer(read_only=True)
    latest_submission = serializers.SerializerMethodField()
    plagiarism = serializers.SerializerMethodField(
        help_text='Aggregated plagiarism similarity summary across submission versions.',
    )

    class Meta:
        model = StudentProjectAssignment
        fields = (
            'id',
            'project_template',
            'status',
            'recommended_by',
            'recommendation_source',
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
            'plagiarism',
        )

    def get_latest_submission(self, obj):
        latest = obj.latest_submission
        return ProjectSubmissionSerializer(latest).data if latest else None

    def get_plagiarism(self, obj):
        latest = obj.latest_submission
        if not latest:
            return {
                'similarity_percent': None,
                'scan_status': 'not_available',
                'source_submission_id': None,
            }
        meta = latest.metadata if isinstance(latest.metadata, dict) else {}
        raw = meta.get('plagiarism_similarity_percent')
        if raw in (None, ''):
            raw = meta.get('copyleaks_similarity_percent')
        value = None
        if raw not in (None, ''):
            try:
                value = round(float(raw), 2)
            except (TypeError, ValueError):
                value = None
        explicit_status = str(
            meta.get('plagiarism_status')
            or meta.get('copyleaks_scan_status')
            or ''
        ).strip().lower()
        if value is not None:
            scan_status = 'completed'
        elif explicit_status:
            scan_status = explicit_status
        elif latest.status == 'SUBMITTED':
            scan_status = 'submitted'
        else:
            scan_status = 'not_available'
        return {
            'similarity_percent': value,
            'scan_status': scan_status,
            'source_submission_id': latest.id,
        }


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
