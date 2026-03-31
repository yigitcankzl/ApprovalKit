from celery import Celery

from api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "approvalkit",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=660,
)

celery_app.autodiscover_tasks(["api.worker"])

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-zombie-jobs": {
        "task": "api.worker.tasks.cleanup_zombie_jobs",
        "schedule": 300.0,  # Every 5 minutes
    },
}
