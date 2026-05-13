from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'

    def ready(self):
        import config  # noqa: F401  — ensures Celery app is loaded
        import projects.signals  # noqa: F401
        import projects.tasks  # noqa: F401
