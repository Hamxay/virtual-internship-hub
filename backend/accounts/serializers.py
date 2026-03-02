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
        validated_data.pop('password_confirm')
        role = validated_data.pop('role', 'STUDENT')
        
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        target_domain_ids = validated_data.pop('target_domain_ids', [])
        current_skill_level = validated_data.pop('current_skill_level', None)
        professional_bio = validated_data.pop('professional_bio', None)
        expertise_domain_id = validated_data.pop('expertise_domain_id', None)
        
        user = User.objects.create_user(role=role, **validated_data)
        
        # Update profile (signal creates it, we just update)
        if role == 'STUDENT' and hasattr(user, 'student_profile'):
            user.student_profile.first_name = first_name or user.username
            user.student_profile.last_name = last_name or ''
            user.student_profile.current_skill_level = current_skill_level
            user.student_profile.save()
            # Add target domains
            if target_domain_ids:
                domains = Domain.objects.filter(id__in=target_domain_ids)
                user.student_profile.target_domains.set(domains)
        elif role == 'MENTOR' and hasattr(user, 'mentor_profile'):
            user.mentor_profile.professional_bio = professional_bio or ''
            if expertise_domain_id:
                domain = Domain.objects.get(id=expertise_domain_id)
                user.mentor_profile.expertise_domain = domain
            user.mentor_profile.save()
        
        return user


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


# --------------- Admin: list students/mentors (no administrator users) ---------------

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

