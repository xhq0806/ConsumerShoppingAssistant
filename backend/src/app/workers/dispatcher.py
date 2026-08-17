"""M1-E Celery 分析任务投递适配器。by AI.Coding"""

from uuid import UUID

from app.core.errors import AnalysisDispatchError
from app.workers.celery_app import celery_app


class CeleryAnalysisTaskDispatcher:
    """通过 Celery broker 投递 comparison_id。by AI.Coding"""

    def dispatch(self, comparison_id: UUID) -> None:
        """投递业务任务并把 broker 异常转换为稳定应用错误。by AI.Coding"""
        try:
            celery_app.send_task(
                "app.workers.process_comparison",
                args=[str(comparison_id)],
            )
        except Exception as error:
            # 不暴露 broker 地址或底层异常，queued 数据库状态保留供客户端重试。
            raise AnalysisDispatchError("任务队列暂时不可用，请稍后重试。") from error
