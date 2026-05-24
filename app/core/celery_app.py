"""
KaPak - Celery Application
Initializes Celery with Redis broker and configures periodic beat schedule.
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "kapak",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.core.tasks.ai_tasks",
        "app.core.tasks.maintenance_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "recalculate-trending-hashtags-every-15m": {
            "task": "app.core.tasks.maintenance_tasks.recalculate_trending_hashtags",
            "schedule": crontab(minute="*/15"),
            "args": ("default",),
        },
        "cleanup-stale-ai-tasks-every-hour": {
            "task": "app.core.tasks.maintenance_tasks.cleanup_stale_ai_tasks",
            "schedule": crontab(minute="0", hour="*/1"),
            "args": ("default",),
        },
        "cleanup-old-search-history-every-6h": {
            "task": "app.core.tasks.maintenance_tasks.cleanup_old_search_history",
            "schedule": crontab(minute="0", hour="*/6"),
            "args": ("default",),
        },
    },
)
