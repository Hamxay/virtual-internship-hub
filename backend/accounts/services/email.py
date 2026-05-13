"""SMTP helpers for signup and password-reset OTP."""
import random
import string
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta


from ..models import PasswordResetOTP, PendingRegistration, User

EMAIL_DISPLAY_NAME = 'Virtual Internship Hub'


def _get_from_email():
    """Return From address with display name so inbox shows 'Virtual Internship Hub' not the raw email."""
    raw = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', 'noreply@example.com')
    raw = (raw or '').strip()
    if not raw:
        return 'noreply@example.com'
    if '<' in raw and '>' in raw:
        return raw
    return f'{EMAIL_DISPLAY_NAME} <{raw}>'


def generate_otp(length=6):
    """Generate a numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))


def create_and_send_password_reset_otp(email):
    """
    Create a new OTP for the given email, invalidate any existing OTPs for that email,
    send OTP by email. Returns (otp_record, True) on success or (None, False) if user not found.
    """
    if not User.objects.filter(email=email).exists():
        return None, False

    expire_minutes = getattr(settings, 'PASSWORD_RESET_OTP_EXPIRE_MINUTES', 2)
    expires_at = timezone.now() + timedelta(minutes=expire_minutes)
    otp = generate_otp(6)

    # Invalidate previous OTPs for this email
    PasswordResetOTP.objects.filter(email=email).delete()

    record = PasswordResetOTP.objects.create(
        email=email,
        otp=otp,
        expires_at=expires_at,
    )

    subject = 'Password Reset OTP - Virtual Internship Hub'
    message = (
        f'Your password reset OTP is: {otp}\n\n'
        f'This code expires in {expire_minutes} minutes. Do not share it with anyone.\n\n'
        'If you did not request this, please ignore this email.'
    )
    from_email = _get_from_email()
    send_mail(
        subject,
        message,
        from_email,
        [email],
        fail_silently=False,
    )
    return record, True


def verify_password_reset_otp(email, otp):
    """
    Verify OTP for the given email. Returns the PasswordResetOTP record if valid, else None.
    """
    try:
        record = PasswordResetOTP.objects.get(email=email, otp=otp)
    except PasswordResetOTP.DoesNotExist:
        return None
    if record.is_expired:
        return None
    return record


def consume_otp(record):
    """Delete OTP after successful password reset."""
    record.delete()


def create_and_send_signup_verification_otp(email, signup_payload):
    """
    Store pending signup and send 6-digit OTP to email.
    signup_payload: dict with password, username, role, first_name, last_name, target_domain_ids, etc.
    Returns (record, True) on success; (None, False) if email already registered.
    """
    if User.objects.filter(email=email).exists():
        return None, False

    expire_minutes = getattr(settings, 'SIGNUP_OTP_EXPIRE_MINUTES', 10)
    expires_at = timezone.now() + timedelta(minutes=expire_minutes)
    otp = generate_otp(6)

    PendingRegistration.objects.filter(email=email).delete()

    record = PendingRegistration.objects.create(
        email=email,
        otp=otp,
        expires_at=expires_at,
        signup_payload=signup_payload,
    )

    subject = 'Verify your email - Virtual Internship Hub'
    message = (
        f'Your verification code is: {otp}\n\n'
        f'This code expires in {expire_minutes} minutes. Do not share it.\n\n'
        'If you did not sign up, please ignore this email.'
    )
    from_email = _get_from_email()
    send_mail(subject, message, from_email, [email], fail_silently=False)
    return record, True


def verify_signup_otp_and_get_payload(email, otp):
    """
    Verify OTP for signup. Returns signup_payload dict if valid, else None.
    Caller should create User and then delete the PendingRegistration.
    """
    try:
        record = PendingRegistration.objects.get(email=email, otp=otp)
    except PendingRegistration.DoesNotExist:
        return None
    if record.is_expired:
        return None
    return record.signup_payload
