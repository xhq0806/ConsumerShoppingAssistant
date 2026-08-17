"""M1-E Celery 业务任务注册测试。by AI.Coding"""

from app.workers.analysis import process_comparison
from app.workers.celery_app import celery_app


def test_process_comparison_task_is_registered_with_stable_name() -> None:
    """Worker 以稳定任务名注册评论采集入口。by AI.Coding"""
    assert process_comparison.name == "app.workers.process_comparison"
    assert "app.workers.process_comparison" in celery_app.tasks
