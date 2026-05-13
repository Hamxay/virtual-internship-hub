"""Assignment/submission hooks: persist notifications, then push over WS after commit."""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from projects.models import ProjectSubmission, StudentProjectAssignment

User = get_user_model()


def _push_notification_ws(user_id: int, data: dict) -> None:
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {'type': 'send_notification', 'data': data},
    )


@receiver(pre_save, sender=StudentProjectAssignment)
def _cache_assignment_status_for_notifications(sender, instance, **kwargs):
    """Stash previous row status so post_save can detect real transitions."""
    if not instance.pk:
        instance._assignment_prev_status = None
        return
    try:
        prev = StudentProjectAssignment.objects.get(pk=instance.pk)
        instance._assignment_prev_status = prev.status
    except StudentProjectAssignment.DoesNotExist:
        instance._assignment_prev_status = None


@receiver(post_save, sender=StudentProjectAssignment)
def notify_student_when_assignment_reviewed(sender, instance, created, **kwargs):
    if created:
        return
    prev = getattr(instance, '_assignment_prev_status', None)
    if prev == instance.status:
        return
    if instance.status not in ('COMPLETED', 'NEEDS_REVISION', 'PENDING_MENTOR_REVIEW'):
        return

    from notifications.models import Notification
    from notifications.serializers import NotificationSerializer

    project_title = getattr(instance.project_template, 'title', 'your project')
    latest_submission = instance.latest_submission
    latest_eval = None
    if latest_submission:
        latest_eval = latest_submission.evaluations.order_by('-reviewed_at', '-id').first()

    if instance.status == 'COMPLETED':
        message = f'Update on "{project_title}": your mentor approved your submission.'
    elif instance.status == 'PENDING_MENTOR_REVIEW':
        message = (
            f'AI evaluation finished for "{project_title}". '
            'Your submission is awaiting mentor review — check your dashboard for feedback.'
        )
    else:
        if latest_eval and latest_eval.is_human_reviewed:
            message = f'Update on "{project_title}": your mentor requested changes.'
        else:
            message = (
                f'AI evaluation finished for "{project_title}". '
                'Please review feedback and resubmit.'
            )

    notif = Notification.objects.create(
        recipient=instance.student,
        message=message,
        link=f'/student/dashboard?task_view=tasks&assignment_id={instance.id}',
    )
    payload = NotificationSerializer(notif).data
    uid = instance.student_id
    transaction.on_commit(lambda: _push_notification_ws(uid, payload))


@receiver(post_save, sender=ProjectSubmission)
def notify_mentors_on_new_submission(sender, instance, created, **kwargs):
    """New submission: notify mentors whose expertise domain matches the project template."""
    if not created:
        return

    from notifications.models import Notification
    from notifications.serializers import NotificationSerializer

    domain_id = instance.assignment.project_template.domain_id
    mentor_ids = list(
        User.objects.filter(
            role='MENTOR',
            mentor_profile__expertise_domain_id=domain_id,
        )
        .values_list('id', flat=True)
        .distinct()
    )

    student_name = (
        getattr(instance.assignment.student, 'username', None)
        or f'Student #{instance.assignment.student_id}'
    )
    project_title = getattr(instance.assignment.project_template, 'title', 'New submission')

    for mentor_id in mentor_ids:
        notif = Notification.objects.create(
            recipient_id=mentor_id,
            message=f'{student_name} submitted "{project_title}" for review.',
            link='/mentor/dashboard',
        )
        payload = NotificationSerializer(notif).data
        transaction.on_commit(
            lambda uid=mentor_id, p=payload: _push_notification_ws(uid, p),
        )
