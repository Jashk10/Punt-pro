from celery import Celery

from moneyball.config.settings import get_settings

settings = get_settings()

app = Celery(
    "moneyball",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["moneyball.celery_app.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Australia/Melbourne",
    enable_utc=True,
)
