from .celery import app as celery_app

# This insures the app is always imported when Django starts.
__all__ = ['celery_app']