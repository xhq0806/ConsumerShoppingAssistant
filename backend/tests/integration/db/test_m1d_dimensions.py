"""M1-D 维度目录、推荐、确认和状态推进 PostgreSQL 集成测试。by AI.Coding"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from conftest import migrated_postgres
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.application.comparisons import (
    ComparisonApplicationService,
    ConfirmDimensionsCommand,
    ConfirmProductsCommand,
    CreateComparisonCommand,
    ProductConfirmation,
    UpdatePreferencesCommand,
)
from app.core.config import Settings
from app.core.errors import DomainConflictError, InputError
from app.infrastructure.db.models import DimensionDefinition, TaskDimension
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.fixture.provider import FixtureCommerceDataProvider

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def migrated_database() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], object]]:
    """启动迁移到 M1-D head 的隔离 PostgreSQL。by AI.Coding"""
    with migrated_postgres("head") as database:
        engine = create_async_engine(database.async_url)
        yield async_sessionmaker(engine, expire_on_commit=False), database.alembic_config
        await engine.dispose()
        command.downgrade(database.alembic_config, "0001")


def _service(
    session_factory: async_sessionmaker[AsyncSession],
) -> ComparisonApplicationService:
    """使用本地 Fixture 和隔离数据库组装真实服务。by AI.Coding"""
    return ComparisonApplicationService(
        lambda: UnitOfWork(session_factory), FixtureCommerceDataProvider(Settings())
    )


async def _confirmed_comparison(
    service: ComparisonApplicationService,
    *,
    idempotency_key: str,
) -> object:
    """创建、解析、确认商品并保存偏好。by AI.Coding"""
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
    return await service.update_preferences(
        confirmed.id,
        UpdatePreferencesCommand(
            review_window_days=60,
            budget_min=Decimal("3000.00"),
            budget_max=Decimal("4500.00"),
            usage_scenarios=("日常通勤", "旅行拍照"),
            priority_concerns=("续航", "拍照"),
            deal_breakers=("机身过重",),
        ),
    )


@pytest.mark.integration
async def test_0006_seeds_common_and_phone_dimensions_without_new_tables(
    migrated_database: tuple[async_sessionmaker[AsyncSession], object],
) -> None:
    """数据迁移注册 16 个维度，并保持成立年份不参与推荐。by AI.Coding"""
    session_factory, _ = migrated_database
    async with session_factory() as session:
        definitions = list(
            await session.scalars(select(DimensionDefinition).order_by(DimensionDefinition.code))
        )
    assert len(definitions) == 16
    assert {item.category for item in definitions} == {None, "手机"}
    founded_year = next(item for item in definitions if item.code == "brand_founded_year")
    assert founded_year.affects_recommendation is False
    assert founded_year.config["description"].startswith("背景信息")


@pytest.mark.integration
async def test_generate_restore_confirm_and_idempotent_queue_boundary(
    migrated_database: tuple[async_sessionmaker[AsyncSession], object],
) -> None:
    """验证维度生成、恢复、调整确认和 queued 幂等闭环。by AI.Coding"""
    session_factory, _ = migrated_database
    service = _service(session_factory)
    comparison = await _confirmed_comparison(service, idempotency_key="m1d-flow-key")

    generated = await service.generate_dimension_recommendations(comparison.id)
    assert generated.generated is True
    assert generated.category == "手机"
    assert len(generated.dimensions) == 16
    selected = [item for item in generated.dimensions if item.selected]
    assert len(selected) == 8
    assert [item.code for item in selected[:2]] == ["battery_life", "camera"]
    assert [item.position for item in selected] == list(range(8))

    before_replay = await service.get_comparison(comparison.id)
    replayed = await service.generate_dimension_recommendations(comparison.id)
    after_replay = await service.get_comparison(comparison.id)
    assert replayed == generated
    assert len(after_replay.events) == len(before_replay.events)

    restored = await service.get_dimensions(comparison.id)
    assert restored == generated
    optional_code = next(item.code for item in restored.dimensions if not item.selected)
    ordered_codes = tuple(
        [selected[1].code, selected[0].code]
        + [item.code for item in selected[2:-1]]
        + [optional_code]
    )
    queued = await service.confirm_dimensions(
        comparison.id, ConfirmDimensionsCommand(ordered_codes)
    )
    assert queued.status == "queued"
    queued_selected = [item for item in queued.dimensions if item.selected]
    assert [item.code for item in queued_selected] == list(ordered_codes)
    assert queued_selected[-1].user_selected is True

    replayed_queue = await service.confirm_dimensions(
        comparison.id, ConfirmDimensionsCommand(ordered_codes)
    )
    assert replayed_queue == queued
    with pytest.raises(DomainConflictError, match="不能再次修改"):
        await service.confirm_dimensions(
            comparison.id,
            ConfirmDimensionsCommand(tuple(reversed(ordered_codes))),
        )
    with pytest.raises(DomainConflictError, match="不允许保存用户偏好"):
        await service.update_preferences(
            comparison.id,
            UpdatePreferencesCommand(
                review_window_days=60,
                budget_min=None,
                budget_max=Decimal("4500.00"),
                usage_scenarios=("日常通勤",),
                priority_concerns=("续航",),
                deal_breakers=(),
            ),
        )

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(TaskDimension).where(TaskDimension.comparison_id == comparison.id)
            )
        )
        assert len(rows) == 16
        assert sum(item.selected for item in rows) == len(ordered_codes)
        assert (
            await session.scalar(
                select(func.count())
                .select_from(DimensionDefinition)
                .where(DimensionDefinition.enabled.is_(True))
            )
            == 16
        )


@pytest.mark.integration
async def test_dimension_confirmation_rejects_empty_or_unknown_selection(
    migrated_database: tuple[async_sessionmaker[AsyncSession], object],
) -> None:
    """无候选、空列表和目录外 code 均不能推进任务。by AI.Coding"""
    session_factory, _ = migrated_database
    service = _service(session_factory)
    comparison = await _confirmed_comparison(service, idempotency_key="m1d-invalid-key")

    with pytest.raises(DomainConflictError, match="先生成"):
        await service.confirm_dimensions(comparison.id, ConfirmDimensionsCommand(("price",)))
    await service.generate_dimension_recommendations(comparison.id)
    with pytest.raises(InputError, match="至少"):
        await service.confirm_dimensions(comparison.id, ConfirmDimensionsCommand(()))
    with pytest.raises(DomainConflictError, match="未生成"):
        await service.confirm_dimensions(
            comparison.id, ConfirmDimensionsCommand(("unknown_dimension",))
        )
