from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "consumer_shopping_assistant",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.analysis"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@celery_app.task(name="app.workers.smoke")  # type: ignore[untyped-decorator]
def smoke() -> dict[str, str]:
    """验证 Worker 与 Broker 的基础连接，不写入业务状态。"""
    return {"status": "ok"}
