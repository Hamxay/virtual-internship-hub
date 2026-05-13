"""Celery entrypoints for async submission evaluation."""
from __future__ import annotations

import logging
import os

from celery import shared_task

from projects.models import ProjectSubmission
from projects.services.evaluation import evaluate_submission_logic

logger = logging.getLogger(__name__)


def delete_uploaded_file_for_submission(submission_id: int) -> None:
    """Clear the FileField and delete the on-disk blob if it still exists."""
    submission = ProjectSubmission.objects.filter(pk=submission_id).first()
    if not submission:
        return

    file_field = submission.uploaded_file
    if not file_field or not getattr(file_field, 'name', None):
        return

    absolute_path = None
    try:
        absolute_path = file_field.path
    except Exception:
        absolute_path = None

    try:
        file_field.delete(save=False)
    except Exception as exc:
        logger.warning('Storage delete failed for submission %s: %s', submission_id, exc)

    ProjectSubmission.objects.filter(pk=submission_id).update(uploaded_file=None)

    if absolute_path and os.path.isfile(absolute_path):
        try:
            os.remove(absolute_path)
        except OSError as exc:
            logger.warning('Janitor os.remove failed for %s: %s', absolute_path, exc)


@shared_task
def async_evaluate_submission(submission_id: int) -> None:
    evaluate_submission_logic(submission_id)
