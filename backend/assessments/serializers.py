from rest_framework import serializers
from accounts.serializers import DomainSerializer
from .models import AssessmentQuestion, StudentAssessmentAttempt


class AssessmentQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentQuestion
        fields = (
            'id', 'text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'complexity', 'order', 'points', 'domain',
        )
        read_only_fields = ('id', 'domain')


# --------------- Student: composed assessment (no correct_option) and submit ---------------

class QuestionForStudentSerializer(serializers.ModelSerializer):
    """MCQ for student: options only, no correct_option."""
    class Meta:
        model = AssessmentQuestion
        fields = ('id', 'text', 'option_a', 'option_b', 'option_c', 'option_d', 'complexity', 'order')
        read_only_fields = ('id',)


class SubmitAnswersSerializer(serializers.Serializer):
    submission_token = serializers.UUIDField(
        help_text='From GET student/assessments/composed/; binds answers to that question set.',
    )
    answers = serializers.ListField(
        child=serializers.DictField(),
        help_text='List of {question_id: int, selected_option: "A"|"B"|"C"|"D"}',
    )

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError('At least one answer is required.')
        for item in value:
            if 'question_id' not in item or 'selected_option' not in item:
                raise serializers.ValidationError('Each item must have question_id and selected_option.')
            try:
                qid = item.get('question_id')
                if qid is None or (isinstance(qid, (int, float)) and int(qid) <= 0):
                    raise serializers.ValidationError('Each question_id must be a positive integer.')
            except (TypeError, ValueError):
                raise serializers.ValidationError('Each question_id must be a positive integer.')
            opt = (item.get('selected_option') or '').strip().upper()
            if opt not in ('A', 'B', 'C', 'D'):
                raise serializers.ValidationError('Each selected_option must be A, B, C, or D.')
        return value

    def validate(self, attrs):
        from .services import get_valid_composed_session, validate_answers_match_session

        request = self.context.get('request')
        if not request or not getattr(request.user, 'is_authenticated', False):
            raise serializers.ValidationError({'detail': 'Authentication required.'})

        token = attrs['submission_token']
        answer_ids = [int(a['question_id']) for a in attrs['answers']]
        try:
            session = get_valid_composed_session(request.user, token)
            validate_answers_match_session(session, answer_ids)
        except ValueError as e:
            raise serializers.ValidationError({'submission_token': [str(e)]}) from e

        attrs['_composed_session'] = session
        return attrs


class ComposedQuestionSerializer(serializers.Serializer):
    """One question in composed assessment (no correct_option)."""
    id = serializers.IntegerField()
    text = serializers.CharField()
    option_a = serializers.CharField()
    option_b = serializers.CharField()
    option_c = serializers.CharField()
    option_d = serializers.CharField()
    complexity = serializers.CharField(required=False, allow_blank=True)
    order = serializers.IntegerField()
    domain_id = serializers.IntegerField()


class ComposedAssessmentSerializer(serializers.Serializer):
    """Composed assessment for student: questions + metadata."""
    questions = ComposedQuestionSerializer(many=True)
    test_domain_ids = serializers.ListField(child=serializers.IntegerField())
    max_attempts = serializers.IntegerField()
    attempt_count = serializers.IntegerField()


class AttemptResultSerializer(serializers.ModelSerializer):
    recommended_domains = DomainSerializer(many=True, read_only=True)
    test_domains = DomainSerializer(many=True, read_only=True)
    assessment_title = serializers.SerializerMethodField()

    class Meta:
        model = StudentAssessmentAttempt
        fields = (
            'id',
            'assessment_title',
            'submitted_at',
            'score',
            'total_points',
            'recommended_domains',
            'test_domains',
            'recommendation_meta',
        )
        read_only_fields = ('id', 'submitted_at', 'score', 'total_points', 'recommendation_meta')

    def get_assessment_title(self, obj):
        return 'Skill Assessment (multi-domain)'
