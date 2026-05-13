from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, StudentProfile, MentorProfile, Domain, SKILL_LEVEL_CHOICES

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ('id', 'name', 'code', 'description')

class StudentProfileSerializer(serializers.ModelSerializer):
    target_domains = DomainSerializer(many=True, read_only=True)
    target_domain_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Domain.objects.all(),
        source='target_domains',
        write_only=True,
        required=False
    )

    def validate_target_domain_ids(self, value):
        """Require 2 to 3 target domains when updating."""
        ids = list(value) if value else []
        if len(ids) < 2:
            raise serializers.ValidationError("Select at least 2 target domains.")
        if len(ids) > 3:
            raise serializers.ValidationError("Select at most 3 target domains.")
        return value

    class Meta:
        model = StudentProfile
        fields = ('first_name', 'last_name', 'phone_number', 'bio', 
                  'current_skill_level', 'target_domains', 'target_domain_ids',
                  'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')


class StudentProfileForMentorListSerializer(StudentProfileSerializer):
    """
    Student list row for mentors: adds domain-scoped progress metrics (prefetched on the view).
    """

    username = serializers.CharField(source='user.username', read_only=True)
    student_id = serializers.IntegerField(source='user.id', read_only=True)
    domain_average = serializers.SerializerMethodField()
    projects_completed = serializers.SerializerMethodField()
    is_at_risk = serializers.SerializerMethodField()
    skill_insights = serializers.SerializerMethodField()
    latest_feedback_summary = serializers.SerializerMethodField()
    activity_summary = serializers.SerializerMethodField()

    class Meta(StudentProfileSerializer.Meta):
        fields = (
            *StudentProfileSerializer.Meta.fields,
            'username',
            'student_id',
            'domain_average',
            'projects_completed',
            'is_at_risk',
            'skill_insights',
            'latest_feedback_summary',
            'activity_summary',
        )

    def _all_domain_assignments(self, obj):
        user = getattr(obj, 'user', None)
        if user is None:
            return []
        return getattr(user, '_mentor_domain_assignments_all', None) or []

    def _completed_domain_assignments(self, obj):
        completed = [a for a in self._all_domain_assignments(obj) if a.status == 'COMPLETED']
        return sorted(completed, key=lambda a: ((a.completed_at or a.assigned_at), a.id))

    def _mentor_domain_metrics(self, obj):
        """Compute once per instance (serializer may call getters separately)."""
        if hasattr(obj, '_mentor_coaching_metrics'):
            return obj._mentor_coaching_metrics
        if not self.context.get('mentor_domain_id'):
            obj._mentor_coaching_metrics = (None, None, False, '')
            return obj._mentor_coaching_metrics
        assignments = self._completed_domain_assignments(obj)
        count = len(assignments)
        scores = []
        latest_feedback = ''
        latest_key = None
        for asn in assignments:
            for sub in asn.submissions.all():
                evals = list(sub.evaluations.all())
                if not evals:
                    continue
                mean_score = sum(float(e.overall_score) for e in evals) / len(evals)
                scores.append(mean_score)
                newest_eval = max(
                    evals,
                    key=lambda e: ((e.reviewed_at or asn.completed_at or asn.assigned_at), e.id),
                )
                if newest_eval.feedback_summary:
                    candidate_key = (newest_eval.reviewed_at or asn.completed_at or asn.assigned_at, newest_eval.id)
                    if latest_key is None or candidate_key > latest_key:
                        latest_key = candidate_key
                        latest_feedback = newest_eval.feedback_summary
                break
        avg = round(sum(scores) / len(scores), 2) if scores else None
        at_risk = avg is not None and avg < 60.0
        obj._mentor_coaching_metrics = (avg, count, at_risk, latest_feedback)
        return obj._mentor_coaching_metrics

    def get_projects_completed(self, obj):
        _, count, _, _ = self._mentor_domain_metrics(obj)
        return count

    def get_domain_average(self, obj):
        avg, _, _, _ = self._mentor_domain_metrics(obj)
        return avg

    def get_is_at_risk(self, obj):
        _, _, at_risk, _ = self._mentor_domain_metrics(obj)
        return at_risk

    def get_latest_feedback_summary(self, obj):
        _, _, _, latest_feedback = self._mentor_domain_metrics(obj)
        return latest_feedback or ''

    def get_activity_summary(self, obj):
        """Active and last completed project in the mentor's domain (from prefetched assignments)."""
        user = getattr(obj, 'user', None)
        if user is None:
            return None
        recent = self._all_domain_assignments(obj)
        if not recent:
            return {
                'current_project_title': None,
                'current_status': None,
                'last_completed_project_title': None,
                'last_completed_at': None,
            }
        status_labels = {
            'RECOMMENDED': 'Recommended',
            'IN_PROGRESS': 'In Progress',
            'SUBMITTED': 'Submitted',
            'NEEDS_REVISION': 'Needs Revision',
            'PENDING_MENTOR_REVIEW': 'Pending Mentor Review',
            'COMPLETED': 'Completed',
        }
        active_statuses = (
            'RECOMMENDED',
            'IN_PROGRESS',
            'SUBMITTED',
            'NEEDS_REVISION',
            'PENDING_MENTOR_REVIEW',
        )
        in_progress = next((a for a in recent if a.status in active_statuses), None)
        completed = [a for a in recent if a.status == 'COMPLETED']
        last_done = None
        if completed:
            last_done = max(completed, key=lambda a: ((a.completed_at or a.assigned_at), a.id))
        return {
            'current_project_title': (
                in_progress.project_template.title if in_progress else None
            ),
            'current_status': (
                status_labels.get(in_progress.status, in_progress.status)
                if in_progress
                else None
            ),
            'last_completed_project_title': (
                last_done.project_template.title if last_done else None
            ),
            'last_completed_at': (
                last_done.completed_at.isoformat() if last_done and last_done.completed_at else None
            ),
        }

    def get_skill_insights(self, obj):
        """
        Domain-scoped growth insight for mentor list rows.
        Logic:
        - Use chronological assignment means in mentor domain.
        - Velocity score = average step delta across the sequence.
        - Trend direction uses practical thresholds to avoid noisy flips.
        - Advice maps directly to trend + current level.
        """
        request = self.context.get('request')
        mentor_domain = None
        if request is not None:
            mentor_profile = getattr(request.user, 'mentor_profile', None)
            mentor_domain = getattr(mentor_profile, 'expertise_domain', None)
        if mentor_domain is None:
            return None

        assignments = self._completed_domain_assignments(obj)
        if len(assignments) < 2:
            return None

        ordered_assignments = sorted(assignments, key=lambda asn: ((asn.completed_at or asn.assigned_at), asn.id))
        chronological_scores = []

        for asn in ordered_assignments:
            if asn.project_template.domain_id != mentor_domain.id:
                continue
            assignment_mean = None
            for sub in asn.submissions.all():
                evals = list(sub.evaluations.all())
                if not evals:
                    continue
                assignment_mean = sum(float(ev.overall_score) for ev in evals) / len(evals)
                break
            if assignment_mean is not None:
                chronological_scores.append(assignment_mean)

        if len(chronological_scores) < 2:
            return None

        deltas = [
            (chronological_scores[idx] - chronological_scores[idx - 1])
            for idx in range(1, len(chronological_scores))
        ]
        velocity = sum(deltas) / len(deltas) if deltas else 0.0
        latest_score = chronological_scores[-1]

        if velocity >= 2.5:
            trend_direction = "UP"
            if latest_score >= 80:
                advice = "Strong growth at a high level. Suggest higher complexity tasks."
            else:
                advice = "Positive trend. Keep momentum with one step-harder tasks and quick feedback."
        elif velocity <= -2.5:
            trend_direction = "DOWN"
            advice = "Consistent decline. Immediate 1-on-1 intervention recommended."
        else:
            trend_direction = "STABLE"
            if latest_score < 60:
                advice = "Performance is flat below baseline. Focus on fundamentals before increasing difficulty."
            else:
                advice = "Steady performance. Maintain current learning path."

        sign = '+' if velocity >= 0 else ''
        return {
            'trend_direction': trend_direction,
            'velocity_score': f'{sign}{round(velocity, 1)}%',
            'actionable_advice': advice,
            'insight_window_projects': len(chronological_scores),
        }


class MentorProfileSerializer(serializers.ModelSerializer):
    expertise_domain = DomainSerializer(read_only=True)
    expertise_domain_id = serializers.PrimaryKeyRelatedField(
        queryset=Domain.objects.all(),
        source='expertise_domain',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = MentorProfile
        fields = ('professional_bio', 'expertise_domain', 'expertise_domain_id',
                  'years_of_experience', 'is_available', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

class UserSerializer(serializers.ModelSerializer):
    student_profile = StudentProfileSerializer(read_only=True)
    mentor_profile = MentorProfileSerializer(read_only=True)
    is_superadmin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'role', 'is_superuser', 'is_superadmin', 'is_email_verified', 'created_at',
                  'student_profile', 'mentor_profile')
        read_only_fields = ('id', 'created_at')

    def get_is_superadmin(self, obj):
        return getattr(obj, 'is_superuser', False)

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    # Student fields
    first_name = serializers.CharField(write_only=True, required=False)
    last_name = serializers.CharField(write_only=True, required=False)
    target_domain_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    current_skill_level = serializers.ChoiceField(
        choices=SKILL_LEVEL_CHOICES, 
        write_only=True, 
        required=False
    )
    
    # Mentor fields
    professional_bio = serializers.CharField(write_only=True, required=False)
    expertise_domain_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password_confirm', 'role',
                  'first_name', 'last_name', 'target_domain_ids', 'current_skill_level',
                  'professional_bio', 'expertise_domain_id')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        
        role = attrs.get('role', 'STUDENT')
        if role == 'ADMINISTRATOR':
            raise serializers.ValidationError(
                "Administrator accounts cannot be created via public registration. "
                "Use Django admin or the create_admin management command."
            )
        if role == 'STUDENT':
            if not attrs.get('first_name') or not attrs.get('last_name'):
                raise serializers.ValidationError("First name and last name required for students")
            ids = attrs.get('target_domain_ids') or []
            if len(ids) < 2:
                raise serializers.ValidationError(
                    {"target_domain_ids": "Select at least 2 target domains."}
                )
            if len(ids) > 3:
                raise serializers.ValidationError(
                    {"target_domain_ids": "Select at most 3 target domains."}
                )
        elif role == 'MENTOR':
            if not attrs.get('professional_bio'):
                raise serializers.ValidationError("Professional bio required for mentors")
            if not attrs.get('expertise_domain_id'):
                raise serializers.ValidationError("Expertise domain required for mentors")
        
        return attrs
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value
    
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value
    
    def validate_expertise_domain_id(self, value):
        if value and not Domain.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid domain selected")
        return value
    
    def create(self, validated_data):
        from .services.registration import create_user_from_verified_signup_payload

        return create_user_from_verified_signup_payload(validated_data)

class CreateAdministratorSerializer(serializers.Serializer):
    """Create an administrator (role=ADMINISTRATOR, is_staff=True, is_superuser=False). Superuser-only."""
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True, max_length=150)
    password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError("Email already exists")
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError("Username already exists")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(role='ADMINISTRATOR', password=password, **validated_data)
        user.is_staff = True   # can log in to Django /admin/
        user.is_superuser = False  # admin role, not super admin
        user.is_email_verified = True  # admins created by superuser are treated as verified
        user.save(update_fields=['is_staff', 'is_superuser', 'is_email_verified'])
        return user

    def to_representation(self, instance):
        return UserSerializer(instance).data


class AuthTokenPairSerializer(serializers.Serializer):
    """JWT pair returned on successful login (OpenAPI / drf-spectacular)."""

    refresh = serializers.CharField(help_text='JWT refresh token')
    access = serializers.CharField(help_text='JWT access token')


class LoginResponseSerializer(serializers.Serializer):
    """Response body for POST /api/auth/login/ (matches LoginView)."""

    user = UserSerializer()
    profile = serializers.JSONField(
        allow_null=True,
        help_text='Student or mentor profile when applicable; null for administrators.',
    )
    tokens = AuthTokenPairSerializer()
    message = serializers.CharField()


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                email=email,
                password=password,
            )
            if not user:
                raise serializers.ValidationError('Invalid email or password')
            if not user.is_active:
                raise serializers.ValidationError('Account is disabled')
            if (user.role == 'STUDENT' or user.role == 'MENTOR') and not user.is_email_verified:
                raise serializers.ValidationError('Please verify your email before logging in.')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Email and password required')
        return attrs


class SendPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)


class VerifySignupOTPSerializer(serializers.Serializer):
    """Email + 6-digit OTP to verify and complete registration."""
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match.'})
        return attrs


class AdminStudentListItemSerializer(serializers.ModelSerializer):
    """For admin panel: student user + profile. Only used for role=STUDENT."""
    student_profile = StudentProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'is_active', 'created_at', 'student_profile')


class AdminMentorListItemSerializer(serializers.ModelSerializer):
    """For admin panel: mentor user + profile. Only used for role=MENTOR."""
    mentor_profile = MentorProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'is_active', 'created_at', 'mentor_profile')

