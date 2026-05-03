"""
All API views in one file. Sections: Auth, Student, Mentor, Admin, Domains.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.db.models import Prefetch

from projects.models import ProjectSubmission, StudentProjectAssignment, SubmissionEvaluation

from .models import User, StudentProfile, MentorProfile, Domain, PendingRegistration
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    LoginResponseSerializer,
    UserSerializer,
    CreateAdministratorSerializer,
    StudentProfileSerializer,
    StudentProfileForMentorListSerializer,
    MentorProfileSerializer,
    DomainSerializer,
    SendPasswordResetOTPSerializer,
    VerifyPasswordResetOTPSerializer,
    ResetPasswordSerializer,
    VerifySignupOTPSerializer,
    AdminStudentListItemSerializer,
    AdminMentorListItemSerializer,
)
from .permissions import IsSuperuser, IsAdministrator
from .services.email import (
    create_and_send_password_reset_otp,
    verify_password_reset_otp,
    consume_otp,
    create_and_send_signup_verification_otp,
    verify_signup_otp_and_get_payload,
)
from .services.registration import create_user_from_verified_signup_payload


def tokens_and_user_response(user):
    """Build auth response with user, profile, and JWT tokens."""
    refresh = RefreshToken.for_user(user)
    profile_data = None
    if user.is_student and hasattr(user, 'student_profile'):
        profile_data = StudentProfileSerializer(user.student_profile).data
    elif user.is_mentor and hasattr(user, 'mentor_profile'):
        profile_data = MentorProfileSerializer(user.mentor_profile).data
    return {
        'user': UserSerializer(user).data,
        'profile': profile_data,
        'tokens': {'refresh': str(refresh), 'access': str(refresh.access_token)},
    }


# --------------- Auth ---------------


class SendSignupOTPView(APIView):
    """POST auth/register/send-otp/ – Validate signup data, store pending, send 6-digit OTP to email."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data.copy()
        payload.pop('password_confirm', None)
        email = payload['email']
        _, ok = create_and_send_signup_verification_otp(email, payload)
        if not ok:
            return Response(
                {'email': ['Email already registered.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'message': 'Verification code sent to your email.'},
            status=status.HTTP_200_OK,
        )


class VerifySignupAndRegisterView(APIView):
    """POST auth/register/verify/ – Verify OTP and create account (User + profile)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifySignupOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        payload = verify_signup_otp_and_get_payload(email, otp)
        if payload is None:
            return Response(
                {'otp': ['Invalid or expired code.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = create_user_from_verified_signup_payload(payload)
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        PendingRegistration.objects.filter(email=email).delete()
        return Response({'message': 'Registration successful'}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST auth/login/ – Login with email/password. Returns JWT tokens."""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary='Login',
        description=(
            'Authenticate with email and password. Returns JWT access/refresh tokens, '
            'the user object, and a role-specific profile when the user is a student or mentor.'
        ),
        request=UserLoginSerializer,
        responses={
            200: LoginResponseSerializer,
            400: OpenApiResponse(
                description=(
                    'Invalid credentials, inactive account, unverified email, or serializer errors '
                    '(typical keys: non_field_errors, email, password).'
                ),
            ),
        },
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.validated_data['user']
        data = tokens_and_user_response(user)
        data['message'] = 'Login successful'
        return Response(data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST auth/logout/ – Blacklist refresh token."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        logout(request)
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)


class SendPasswordResetOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendPasswordResetOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        email = serializer.validated_data['email']
        _, ok = create_and_send_password_reset_otp(email)
        if not ok:
            return Response({'email': 'No account found with this email.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'message': 'OTP sent to your email. It expires in 2 minutes.'}, status=status.HTTP_200_OK)


class VerifyPasswordResetOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyPasswordResetOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        record = verify_password_reset_otp(email, otp)
        if not record:
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'OTP verified. You can now reset your password.'}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        record = verify_password_reset_otp(email, otp)
        if not record:
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new_password)
        except ValidationError as e:
            return Response({'new_password': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'email': 'No account found with this email.'}, status=status.HTTP_404_NOT_FOUND)
        user.set_password(new_password)
        user.save()
        consume_otp(record)
        return Response({'message': 'Password reset successful. You can now log in.'}, status=status.HTTP_200_OK)


class ResendPasswordResetOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendPasswordResetOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        email = serializer.validated_data['email']
        _, ok = create_and_send_password_reset_otp(email)
        if not ok:
            return Response({'email': 'No account found with this email.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'message': 'New OTP sent. It expires in 2 minutes.'}, status=status.HTTP_200_OK)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT auth/profile/ – Current user profile."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# --------------- Student ---------------

class StudentProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT students/profile/ – Student profile (students only)."""
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile = getattr(self.request.user, 'student_profile', None)
        if profile is None:
            raise NotFound('Student profile not found.')
        return profile

    def get(self, request, *args, **kwargs):
        if not request.user.is_student:
            return Response({'error': 'Only students can access this.'}, status=status.HTTP_403_FORBIDDEN)
        return super().get(request, *args, **kwargs)


class StudentListView(generics.ListAPIView):
    """GET students/ – List students. Admins see all; mentors see only students whose target domains include the mentor's expertise domain."""
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.user.is_mentor:
            return StudentProfileForMentorListSerializer
        return StudentProfileSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.user.is_mentor:
            mp = getattr(self.request.user, 'mentor_profile', None)
            if mp and mp.expertise_domain_id:
                ctx['mentor_domain_id'] = mp.expertise_domain_id
        return ctx

    def get_queryset(self):
        user = self.request.user
        if user.is_administrator:
            return StudentProfile.objects.select_related('user').prefetch_related('target_domains').all()
        if user.is_mentor:
            profile = getattr(user, 'mentor_profile', None)
            if not profile or not profile.expertise_domain_id:
                return StudentProfile.objects.none()
            domain_id = profile.expertise_domain_id
            completed_in_domain = (
                StudentProjectAssignment.objects.filter(
                    status='COMPLETED',
                    project_template__domain_id=domain_id,
                )
                .select_related('project_template', 'project_template__domain')
                .prefetch_related(
                    Prefetch(
                        'submissions',
                        queryset=ProjectSubmission.objects.prefetch_related(
                            Prefetch('evaluations', queryset=SubmissionEvaluation.objects.all()),
                        ).order_by('-submitted_at', '-id'),
                    ),
                )
            )
            return (
                StudentProfile.objects.filter(target_domains=profile.expertise_domain)
                .select_related('user')
                .prefetch_related(
                    'target_domains',
                    Prefetch(
                        'user__project_assignments',
                        queryset=completed_in_domain,
                        to_attr='_prefetched_completed_domain_assignments',
                    ),
                )
                .distinct()
            )
        return StudentProfile.objects.none()


# --------------- Mentor ---------------

class MentorProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT mentors/profile/ – Mentor profile (mentors only)."""
    serializer_class = MentorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile = getattr(self.request.user, 'mentor_profile', None)
        if profile is None:
            raise NotFound('Mentor profile not found.')
        return profile

    def get(self, request, *args, **kwargs):
        if not request.user.is_mentor:
            return Response({'error': 'Only mentors can access this.'}, status=status.HTTP_403_FORBIDDEN)
        return super().get(request, *args, **kwargs)


class MentorListView(generics.ListAPIView):
    """GET mentors/ – List mentors."""
    serializer_class = MentorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_student:
            return MentorProfile.objects.filter(is_available=True)
        return MentorProfile.objects.all()


# --------------- Admin ---------------

class CreateAdministratorView(generics.CreateAPIView):
    """POST admin/administrators/ – Create administrator (superuser only)."""
    permission_classes = [permissions.IsAuthenticated, IsSuperuser]
    serializer_class = CreateAdministratorSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminStudentListView(generics.ListAPIView):
    """GET admin/users/students/ – List all students (admin only). Paginated."""
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = AdminStudentListItemSerializer
    queryset = User.objects.filter(role='STUDENT').select_related('student_profile').prefetch_related('student_profile__target_domains')


class AdminMentorListView(generics.ListAPIView):
    """GET admin/users/mentors/ – List all mentors (admin only). Paginated."""
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = AdminMentorListItemSerializer
    queryset = User.objects.filter(role='MENTOR').select_related('mentor_profile', 'mentor_profile__expertise_domain')


# --------------- Domains (shared) ---------------

class DomainListView(generics.ListAPIView):
    """GET domains/ – List domains (public, unpaginated)."""
    serializer_class = DomainSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Domain.objects.all()
    pagination_class = None


# --------------- Admin: Domain CRUD ---------------

class AdminDomainPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class AdminDomainListCreateView(generics.ListCreateAPIView):
    """GET/POST admin/domains/ – List or create domains (admin only). Paginated."""
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = DomainSerializer
    queryset = Domain.objects.all().order_by('name')
    pagination_class = AdminDomainPagination


class AdminDomainDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE admin/domains/<pk>/ – One domain (admin only)."""
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    serializer_class = DomainSerializer
    queryset = Domain.objects.all()
