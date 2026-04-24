from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'

    def ready(self):
        # Load package Celery app and register ``projects.tasks`` for ``.delay()`` from Django.
        import config  # noqa: F401
        import projects.signals  # noqa: F401 — FR10 notifications
        import projects.tasks  # noqa: F401
