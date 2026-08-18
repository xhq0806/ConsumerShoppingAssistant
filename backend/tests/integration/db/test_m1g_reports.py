"""M1-G 报告发布、降级终态、幂等与重试 PostgreSQL 集成测试。by AI.Coding"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from conftest import migrated_postgres
from sqlalchemy import func, select
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
from app.application.report_generation import (
    GatewayPurchaseReportGenerator,
    PurchaseReportInvocationFailure,
    ReportApplicationService,
)
from app.application.review_analysis import GatewayReviewAnnotationAnalyzer
from app.core.config import Settings
from app.core.errors import DomainConflictError, LLMTimeoutError
from app.domain.reports import ReportClaimType, ReportStatus
from app.domain.reports.generation import ReportGenerationContext
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.models import ComparisonReport, ModelRun, ReportClaim
from app.infrastructure.db.report_repository import ReportRepository
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.fixture.provider import FixtureCommerceDataProvider
from app.providers.llm.base import LLMAuditEvent, TokenUsage

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
    """记录 retry/start 投递且不连接测试 Redis。by AI.Coding"""

    def __init__(self) -> None:
        """初始化稳定投递记录。by AI.Coding"""
        self.dispatched: list[UUID] = []

    def dispatch(self, comparison_id: UUID) -> None:
        """记录单次任务投递。by AI.Coding"""
        self.dispatched.append(comparison_id)


class _TimeoutReportGenerator:
    """稳定模拟 report profile 超时。by AI.Coding"""

    async def generate(
        self,
        *,
        context: ReportGenerationContext,
        trace_id: str,
    ):
        """返回不含报告输入正文的受控 LLM 超时。by AI.Coding"""
        assert context.products and context.dimensions
        error = LLMTimeoutError("模型调用超过配置的时间限制。")
        event = LLMAuditEvent(
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            purpose="purchase_report",
            provider="fake",
            model="fake-report-timeout",
            trace_id=trace_id,
            prompt_version="m1g-purchase-report-v1",
            status="error",
            latency_ms=1,
            attempts=1,
            usage=TokenUsage(),
            error_code=error.code,
        )
        raise PurchaseReportInvocationFailure(error, event)


def _uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
):
    """构造每次返回独立 UnitOfWork 的工厂。by AI.Coding"""
    return lambda: UnitOfWork(session_factory)


async def _queued_comparison(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    idempotency_key: str,
) -> UUID:
    """执行 M1-B 至 M1-D 前置流程并返回 queued 任务。by AI.Coding"""
    service = ComparisonApplicationService(
        _uow_factory(session_factory),
        FixtureCommerceDataProvider(Settings()),
    )
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
            priority_concerns=("价格", "拍照"),
            deal_breakers=(),
        ),
    )
    dimensions = await service.generate_dimension_recommendations(confirmed.id)
    selected_codes = tuple(item.code for item in dimensions.dimensions if item.selected)
    await service.confirm_dimensions(confirmed.id, ConfirmDimensionsCommand(selected_codes))
    return confirmed.id


def _analysis_service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    commerce_provider: FixtureCommerceDataProvider,
    report_generator: GatewayPurchaseReportGenerator | _TimeoutReportGenerator,
    dispatcher: _RecordingDispatcher | None,
) -> AnalysisApplicationService:
    """组装包含 M1-F 与 M1-G 的完整 Worker 应用服务。by AI.Coding"""
    uow_factory = _uow_factory(session_factory)
    report_service = ReportApplicationService(uow_factory, report_generator)
    return AnalysisApplicationService(
        uow_factory,
        commerce_provider,
        dispatcher=dispatcher,
        annotation_analyzer=GatewayReviewAnnotationAnalyzer(Settings()),
        report_service=report_service,
    )


@pytest.mark.integration
async def test_report_generation_publishes_partial_terminal_and_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Fixture 缺失字段生成 version=1 降级报告并推进 partially_completed/100。by AI.Coding"""
    comparison_id = await _queued_comparison(
        session_factory,
        idempotency_key="m1g-report-success",
    )
    service = _analysis_service(
        session_factory,
        commerce_provider=FixtureCommerceDataProvider(Settings()),
        report_generator=GatewayPurchaseReportGenerator(Settings()),
        dispatcher=_RecordingDispatcher(),
    )

    result = await service.process_comparison(comparison_id)
    assert result.status == "partially_completed"
    progress = await service.get_analysis_progress(comparison_id)
    assert progress.status == "partially_completed"
    assert progress.progress == 100
    assert progress.stage == "partially_completed"
    assert progress.polling_complete is True

    report_view = await ReportApplicationService(_uow_factory(session_factory)).get_latest_report(
        comparison_id
    )
    assert report_view.version == 1
    assert report_view.status == "partial"
    assert report_view.summary["recommended_product_id"] is not None
    assert report_view.claims
    assert any("品牌" in warning for warning in report_view.warnings)
    assert any("有效评论" in warning for warning in report_view.warnings)
    assert report_view.full_comparison["products"]

    duplicate = await service.process_comparison(comparison_id)
    assert duplicate.outcome == "ignored"
    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ComparisonReport)
                .where(ComparisonReport.comparison_id == comparison_id)
            )
            == 1
        )
        assert await session.scalar(
            select(func.count())
            .select_from(ReportClaim)
            .join(ComparisonReport)
            .where(ComparisonReport.comparison_id == comparison_id)
        ) == len(report_view.claims)


@pytest.mark.integration
async def test_report_timeout_publishes_deterministic_partial_fallback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """报告超时记录错误审计并使用确定性基础报告完成任务。by AI.Coding"""
    comparison_id = await _queued_comparison(
        session_factory,
        idempotency_key="m1g-report-retry",
    )
    failing_service = _analysis_service(
        session_factory,
        commerce_provider=FixtureCommerceDataProvider(Settings()),
        report_generator=_TimeoutReportGenerator(),
        dispatcher=_RecordingDispatcher(),
    )

    result = await failing_service.process_comparison(comparison_id)
    assert result.status == "partially_completed"
    progress = await failing_service.get_analysis_progress(comparison_id)
    assert progress.progress == 100
    assert progress.can_retry is False
    assert progress.metric_count == 144

    async with session_factory() as session:
        reports = list(
            await session.scalars(
                select(ComparisonReport).where(ComparisonReport.comparison_id == comparison_id)
            )
        )
        runs = list(
            await session.scalars(select(ModelRun).where(ModelRun.comparison_id == comparison_id))
        )
    assert len(reports) == 1
    assert reports[0].version == 1
    assert reports[0].status.value == "partial"
    assert any("报告模型暂不可用" in warning for warning in reports[0].warnings)
    assert [run.purpose for run in runs] == ["review_annotation", "purchase_report"]
    assert runs[-1].error_code == "LLM_TIMEOUT"


@pytest.mark.integration
async def test_report_publish_rejects_snapshot_from_another_comparison(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """来源 UUID 结构正确但属于其他任务时不得发布报告。by AI.Coding"""
    first_id = await _queued_comparison(
        session_factory,
        idempotency_key="m1g-source-owner-first",
    )
    second_id = await _queued_comparison(
        session_factory,
        idempotency_key="m1g-source-owner-second",
    )

    async with session_factory() as session:
        first = await ComparisonRepository(session).get_detail(first_id)
        second = await ComparisonRepository(session).get_detail(second_id)
        assert first is not None and second is not None
        foreign_snapshot = second.products[0].snapshots[0]
        report = ComparisonReport(
            comparison_id=first.id,
            version=1,
            status=ReportStatus.GENERATING,
        )
        report.claims.append(
            ReportClaim(
                claim_type=ReportClaimType.FACT,
                text="错误引用了其他任务的价格。",
                source_refs=[
                    {
                        "type": "product_snapshot",
                        "id": str(foreign_snapshot.id),
                        "field": "price",
                    }
                ],
                confidence=0.5,
                display_order=0,
            )
        )
        session.add(report)
        await session.flush()

        with pytest.raises(DomainConflictError, match="来源不存在"):
            await ReportRepository(session).publish(report, ReportStatus.PARTIAL)
        await session.rollback()
