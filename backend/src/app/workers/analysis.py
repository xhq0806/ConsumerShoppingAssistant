"""M1-E Celery 评论采集业务任务。by AI.Coding"""

import asyncio
from uuid import UUID

from app.application.analysis_tasks import AnalysisApplicationService
from app.application.report_generation import (
    GatewayPurchaseReportGenerator,
    ReportApplicationService,
)
from app.application.review_analysis import GatewayReviewAnnotationAnalyzer
from app.core.config import get_settings
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.fixture.provider import FixtureCommerceDataProvider
from app.workers.celery_app import celery_app


async def _run_process_comparison(comparison_id: UUID) -> dict[str, object]:
    """在单次 Celery 任务事件循环内创建并释放数据库连接池。by AI.Coding"""
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:

        def uow_factory() -> UnitOfWork:
            """为报告和分析阶段创建共享 session factory 的独立工作单元。by AI.Coding"""
            return UnitOfWork(session_factory)

        report_service = ReportApplicationService(
            uow_factory,
            GatewayPurchaseReportGenerator(settings),
        )
        service = AnalysisApplicationService(
            uow_factory,
            FixtureCommerceDataProvider(settings),
            dispatcher=None,
            annotation_analyzer=GatewayReviewAnnotationAnalyzer(settings),
            report_service=report_service,
            max_reviews_per_product=settings.review_max_per_product,
        )
        result = await service.process_comparison(comparison_id)
        return {
            "comparison_id": str(result.comparison_id),
            "outcome": result.outcome,
            "status": result.status,
            "fetched_review_count": result.fetched_review_count,
            "valid_review_count": result.valid_review_count,
            "annotated_review_count": result.annotated_review_count,
            "annotation_count": result.annotation_count,
            "metric_count": result.metric_count,
        }
    finally:
        # asyncio.run 即将关闭事件循环，必须先释放绑定该循环的 asyncpg 连接池。
        await engine.dispose()


@celery_app.task(name="app.workers.process_comparison")  # type: ignore[untyped-decorator]
def process_comparison(comparison_id: str) -> dict[str, object]:
    """把同步 Celery task 桥接到异步评论采集用例。by AI.Coding"""
    return asyncio.run(_run_process_comparison(UUID(comparison_id)))
