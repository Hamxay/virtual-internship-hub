"""Create ``User`` + role profile after signup OTP verification."""
from ..models import User, Domain


def create_user_from_verified_signup_payload(payload):
    """Build user from OTP-verified payload; sets ``is_email_verified``."""
    data = dict(payload)
    data.pop('password_confirm', None)
    role = data.pop('role', 'STUDENT')
    first_name = data.pop('first_name', None)
    last_name = data.pop('last_name', None)
    target_domain_ids = data.pop('target_domain_ids', []) or []
    current_skill_level = data.pop('current_skill_level', None)
    professional_bio = data.pop('professional_bio', None)
    expertise_domain_id = data.pop('expertise_domain_id', None)

    user = User.objects.create_user(role=role, **data)
    user.is_email_verified = True
    user.save(update_fields=['is_email_verified'])

    if role == 'STUDENT' and hasattr(user, 'student_profile'):
        user.student_profile.first_name = first_name or user.username
        user.student_profile.last_name = last_name or ''
        user.student_profile.current_skill_level = current_skill_level
        user.student_profile.save()
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
