"""M1-B FastAPI 可替换依赖工厂。by AI.Coding"""

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.analysis_tasks import AnalysisApplicationService
from app.application.comparisons import ComparisonApplicationService
from app.core.config import Settings, get_settings
from app.infrastructure.db.dependencies import session_factory
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.commerce.base import CommerceDataProvider
from app.providers.fixture.provider import FixtureCommerceDataProvider
from app.workers.dispatcher import CeleryAnalysisTaskDispatcher


@lru_cache
def get_commerce_provider() -> CommerceDataProvider:
    """返回开发基线唯一允许的无网络 Fixture Provider。by AI.Coding"""
    settings: Settings = get_settings()
    # M1-B 明确不接入真实淘宝，未知 provider 也不能静默降级为外部连接。
    if settings.commerce_provider != "fixture":
        raise RuntimeError("M1-B 仅支持 fixture Commerce Provider")
    return FixtureCommerceDataProvider(settings)


def get_uow_factory() -> Callable[[], UnitOfWork]:
    """提供绑定应用数据库 session factory 的短事务工厂。by AI.Coding"""
    factory: async_sessionmaker[AsyncSession] = session_factory
    # 返回闭包而非共享 UoW，保证每次用例分段均使用独立会话和事务。
    return lambda: UnitOfWork(factory)


def get_comparison_service(
    commerce_provider: Annotated[CommerceDataProvider, Depends(get_commerce_provider)],
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
) -> ComparisonApplicationService:
    """组装路由所需的 M1-B application service。by AI.Coding"""
    # 依赖替换入口集中在此，路由保持不感知 ORM 与 Provider 实现。
    return ComparisonApplicationService(uow_factory, commerce_provider)


@lru_cache
def get_analysis_dispatcher() -> CeleryAnalysisTaskDispatcher:
    """返回 API 进程使用的 Celery 分析任务调度器。by AI.Coding"""
    return CeleryAnalysisTaskDispatcher()


def get_analysis_service(
    commerce_provider: Annotated[CommerceDataProvider, Depends(get_commerce_provider)],
    uow_factory: Annotated[Callable[[], UnitOfWork], Depends(get_uow_factory)],
    dispatcher: Annotated[CeleryAnalysisTaskDispatcher, Depends(get_analysis_dispatcher)],
) -> AnalysisApplicationService:
    """组装分析启动、重试和进度查询应用服务。by AI.Coding"""
    settings = get_settings()
    return AnalysisApplicationService(
        uow_factory,
        commerce_provider,
        dispatcher=dispatcher,
        max_reviews_per_product=settings.review_max_per_product,
    )
