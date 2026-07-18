from celery import Celery

from medreg.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "medreg",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "medreg.modules.documents.tasks",
        "medreg.modules.retrieval.tasks",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    result_expires=3600,
    broker_transport_options={"visibility_timeout": 1800},
    beat_schedule={
        "recover-stale-document-jobs": {
            "task": "medreg.documents.recover_stale",
            "schedule": 60.0,
        }
    },
)
