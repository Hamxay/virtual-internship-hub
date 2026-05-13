"""Account routes (mounted under ``/api/``)."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    SendSignupOTPView,
    VerifySignupAndRegisterView,
    LoginView,
    LogoutView,
    SendPasswordResetOTPView,
    VerifyPasswordResetOTPView,
    ResetPasswordView,
    ResendPasswordResetOTPView,
    UserProfileView,
    StudentProfileView,
    StudentListView,
    MentorProfileView,
    MentorListView,
    CreateAdministratorView,
    AdminStudentListView,
    AdminMentorListView,
    DomainListView,
    AdminDomainListCreateView,
    AdminDomainDetailView,
)

urlpatterns = [
    path('auth/register/send-otp/', SendSignupOTPView.as_view(), name='auth-register-send-otp'),
    path('auth/register/verify/', VerifySignupAndRegisterView.as_view(), name='auth-register-verify'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('auth/forgot-password/send-otp/', SendPasswordResetOTPView.as_view(), name='auth-forgot-send-otp'),
    path('auth/forgot-password/verify-otp/', VerifyPasswordResetOTPView.as_view(), name='auth-forgot-verify-otp'),
    path('auth/forgot-password/reset/', ResetPasswordView.as_view(), name='auth-forgot-reset'),
    path('auth/forgot-password/resend-otp/', ResendPasswordResetOTPView.as_view(), name='auth-forgot-resend-otp'),
    path('auth/profile/', UserProfileView.as_view(), name='auth-profile'),
    # --------------- Student ---------------
    path('students/profile/', StudentProfileView.as_view(), name='student-profile'),
    path('students/', StudentListView.as_view(), name='student-list'),
    path('mentors/profile/', MentorProfileView.as_view(), name='mentor-profile'),
    path('mentors/', MentorListView.as_view(), name='mentor-list'),
    path('admin/administrators/', CreateAdministratorView.as_view(), name='admin-create-administrator'),
    path('admin/users/students/', AdminStudentListView.as_view(), name='admin-users-students'),
    path('admin/users/mentors/', AdminMentorListView.as_view(), name='admin-users-mentors'),
    path('admin/domains/', AdminDomainListCreateView.as_view(), name='admin-domain-list-create'),
    path('admin/domains/<int:pk>/', AdminDomainDetailView.as_view(), name='admin-domain-detail'),
    path('domains/', DomainListView.as_view(), name='domain-list'),
]
