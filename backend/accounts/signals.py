"""Wire profile creation when a ``User`` is saved."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, StudentProfile, MentorProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create StudentProfile or MentorProfile when a new User is created."""
    if not created:
        return
    if instance.is_student:
        StudentProfile.objects.create(
            user=instance,
            first_name=instance.username,
            last_name='',
        )
    elif instance.is_mentor:
        MentorProfile.objects.create(
            user=instance,
            professional_bio='',
        )
