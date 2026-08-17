"""M1-E 异步评论采集、失败原子性和重试 PostgreSQL 集成测试。by AI.Coding"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from conftest import migrated_postgres
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.application.analysis_tasks import AnalysisApplicationService
from app.application.comparisons import (
    ComparisonApplicationService,
    ConfirmDimensionsCommand,
    ConfirmProductsCommand,
    CreateComparisonCommand,
    ProductConfirmation,
    UpdatePreferencesCommand,
)
from app.core.config import Settings
from app.core.errors import DomainConflictError, ProviderUnavailableError
from app.infrastructure.db.models import RawReview
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.commerce.dto import (
    ProductProviderResult,
    ProductRequest,
    ReviewFetchRequest,
    ReviewProviderResult,
)
from app.providers.fixture.provider import FixtureCommerceDataProvider
from app.workers.analysis import process_comparison

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """启动迁移到当前 head 的隔离 PostgreSQL。by AI.Coding"""
    with migrated_postgres("head") as database:
        engine = create_async_engine(database.async_url)
        yield async_sessionmaker(engine, expire_on_commit=False)
        await engine.dispose()
        command.downgrade(database.alembic_config, "0001")


class _RecordingDispatcher:
    """记录 API 投递 comparison_id，避免测试连接真实 Redis。by AI.Coding"""

    def __init__(self) -> None:
        self.dispatched: list[UUID] = []

    def dispatch(self, comparison_id: UUID) -> None:
        """记录一次异步任务投递。by AI.Coding"""
        self.dispatched.append(comparison_id)


class _SecondProductUnavailableProvider:
    """首商品成功、第二商品失败的受控 Provider。by AI.Coding"""

    def __init__(self) -> None:
        self._delegate = FixtureCommerceDataProvider(Settings())

    async def normalize_url(self, url: str):
        """复用 Fixture URL 安全规范化。by AI.Coding"""
        return await self._delegate.normalize_url(url)

    async def fetch_product(self, request: ProductRequest) -> ProductProviderResult:
        """复用 Fixture 商品解析。by AI.Coding"""
        return await self._delegate.fetch_product(request)

    async def fetch_reviews(self, request: ReviewFetchRequest) -> ReviewProviderResult:
        """第二个商品模拟可重试 Provider 不可用。by AI.Coding"""
        if request.product_url.external_product_id == "10002":
            raise ProviderUnavailableError("Fixture 模拟评论服务暂不可用。")
        return await self._delegate.fetch_reviews(request)


def _comparison_service(
    session_factory: async_sessionmaker[AsyncSession],
) -> ComparisonApplicationService:
    """组装真实 Comparison 前置流程。by AI.Coding"""
    return ComparisonApplicationService(
        lambda: UnitOfWork(session_factory),
        FixtureCommerceDataProvider(Settings()),
    )


def _analysis_service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    dispatcher: _RecordingDispatcher | None,
    failing: bool = False,
) -> AnalysisApplicationService:
    """组装真实或受控失败的分析服务。by AI.Coding"""
    provider = (
        _SecondProductUnavailableProvider() if failing else FixtureCommerceDataProvider(Settings())
    )
    return AnalysisApplicationService(
        lambda: UnitOfWork(session_factory),
        provider,
        dispatcher=dispatcher,
    )


async def _queued_comparison(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    idempotency_key: str,
) -> UUID:
    """执行 M1-B 至 M1-D 前置流程并返回 queued 任务 ID。by AI.Coding"""
    service = _comparison_service(session_factory)
    created = await service.create_comparison(
        CreateComparisonCommand(
            (
                "https://item.taobao.com/item.htm?id=10001",
                "https://item.taobao.com/item.htm?id=10002",
            ),
            30,
        ),
        idempotency_key=idempotency_key,
    )
    parsed = await service.parse_products(created.id)
    confirmed = await service.confirm_products(
        created.id,
        ConfirmProductsCommand(
            tuple(
                ProductConfirmation(
                    product.id,
                    None if not product.skus else product.skus[0].id,
                )
                for product in parsed.products
            )
        ),
    )
    await service.update_preferences(
        confirmed.id,
        UpdatePreferencesCommand(
            review_window_days=30,
            budget_min=Decimal("3000.00"),
            budget_max=Decimal("4500.00"),
            usage_scenarios=("日常通勤",),
            priority_concerns=("续航", "拍照"),
            deal_breakers=(),
        ),
    )
    dimensions = await service.generate_dimension_recommendations(confirmed.id)
    selected_codes = tuple(item.code for item in dimensions.dimensions if item.selected)
    await service.confirm_dimensions(confirmed.id, ConfirmDimensionsCommand(selected_codes))
    return confirmed.id


@pytest.mark.integration
async def test_dispatch_process_clean_persist_and_ignore_duplicate_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """真实 Fixture 评论清洗入库，重复 Worker 消息不会重复执行。by AI.Coding"""
    comparison_id = await _queued_comparison(session_factory, idempotency_key="m1e-success-key")
    dispatcher = _RecordingDispatcher()
    service = _analysis_service(session_factory, dispatcher=dispatcher)

    started = await service.request_analysis(comparison_id)
    assert started.status == "queued"
    assert dispatcher.dispatched == [comparison_id]

    results = await asyncio.gather(
        service.process_comparison(comparison_id),
        service.process_comparison(comparison_id),
    )
    assert {result.outcome for result in results} == {"processed", "ignored"}
    processed = next(result for result in results if result.outcome == "processed")
    assert processed.fetched_review_count == 3
    assert processed.valid_review_count == 2

    progress = await service.get_analysis_progress(comparison_id)
    assert progress.status == "processing"
    assert progress.progress == 45
    assert progress.stage == "review_data_ready"
    assert progress.fetched_review_count == 3
    assert progress.valid_review_count == 2
    assert progress.polling_complete is True

    async with session_factory() as session:
        reviews = list(
            await session.scalars(
                select(RawReview).order_by(RawReview.reviewed_at, RawReview.external_review_id)
            )
        )
    assert len(reviews) == 2
    assert any("忽略此前规则" in review.content for review in reviews)
    assert len({review.content_hash for review in reviews}) == 2


@pytest.mark.integration
async def test_provider_failure_persists_no_partial_reviews_and_can_retry(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """第二商品失败时首商品结果不入库，可重试任务重新排队。by AI.Coding"""
    comparison_id = await _queued_comparison(session_factory, idempotency_key="m1e-retry-key")
    failing_service = _analysis_service(
        session_factory, dispatcher=_RecordingDispatcher(), failing=True
    )

    failed = await failing_service.process_comparison(comparison_id)
    assert failed.outcome == "failed"
    progress = await failing_service.get_analysis_progress(comparison_id)
    assert progress.status == "failed"
    assert progress.can_retry is True
    assert progress.valid_review_count == 0

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(RawReview)
                .join(RawReview.comparison_product)
                .where(RawReview.comparison_product.has(comparison_id=comparison_id))
            )
            is None
        )

    dispatcher = _RecordingDispatcher()
    retry_service = _analysis_service(session_factory, dispatcher=dispatcher)
    retried = await retry_service.retry_analysis(comparison_id)
    assert retried.status == "queued"
    assert dispatcher.dispatched == [comparison_id]

    processed = await retry_service.process_comparison(comparison_id)
    assert processed.status == "processing"
    with pytest.raises(DomainConflictError, match="不允许重试"):
        await retry_service.retry_analysis(comparison_id)


@pytest.mark.integration
async def test_sync_celery_bridge_processes_two_tasks_without_reusing_closed_loop_pool(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """同一 Worker 进程连续任务各自创建连接池，不复用已关闭事件循环连接。by AI.Coding"""
    first_id = await _queued_comparison(session_factory, idempotency_key="m1e-worker-loop-first")
    second_id = await _queued_comparison(session_factory, idempotency_key="m1e-worker-loop-second")

    first = await asyncio.to_thread(process_comparison.run, str(first_id))
    second = await asyncio.to_thread(process_comparison.run, str(second_id))

    assert first["status"] == "processing"
    assert second["status"] == "processing"
    assert first["valid_review_count"] == 2
    assert second["valid_review_count"] == 2
