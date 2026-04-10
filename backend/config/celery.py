"""
Celery application for async tasks (e.g. FR4 AI evaluation).

Run worker: ``celery -A config worker -l info``
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
