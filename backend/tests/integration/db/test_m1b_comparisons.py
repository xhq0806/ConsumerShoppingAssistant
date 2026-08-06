"""M1-B PostgreSQL 幂等迁移与仓储集成测试。by AI.Coding"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from conftest import migrated_postgres
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.application.comparisons import (
    ComparisonApplicationService,
    ConfirmProductsCommand,
    CreateComparisonCommand,
    ProductConfirmation,
)
from app.core.config import Settings
from app.domain.comparisons import TaskEventType, TaskStage
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.models import ComparisonTask
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.fixture.provider import FixtureCommerceDataProvider

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """启动迁移至 M1-B head 的隔离 PostgreSQL 数据库。by AI.Coding"""
    with migrated_postgres("head") as database:
        engine = create_async_engine(database.async_url)
        yield async_sessionmaker(engine, expire_on_commit=False)
        await engine.dispose()
        # 生命周期测试随后回退到 M1-A 基线，避免容器退出掩盖 downgrade 问题。
        command.downgrade(database.alembic_config, "0001")


@pytest.mark.integration
async def test_idempotency_columns_pair_and_non_null_hash_is_unique(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 0005 的成对 CHECK 与部分唯一索引。by AI.Coding"""
    async with session_factory() as session:
        # 半套幂等数据必须由数据库拒绝，不能仅依赖应用校验。
        invalid = ComparisonTask(review_window_days=30)
        invalid.idempotency_key_hash = "a" * 64
        session.add(invalid)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

        first = ComparisonTask(
            review_window_days=30,
            idempotency_key_hash="a" * 64,
            create_request_fingerprint="b" * 64,
        )
        second = ComparisonTask(
            review_window_days=60,
            idempotency_key_hash="a" * 64,
            create_request_fingerprint="c" * 64,
        )
        session.add_all([first, second])
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.integration
async def test_repository_reads_idempotency_and_writes_event_without_commit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证仓储集中事件入口、聚合读取与调用方事务边界。by AI.Coding"""
    async with session_factory() as session:
        task = ComparisonTask(
            review_window_days=30,
            idempotency_key_hash="d" * 64,
            create_request_fingerprint="e" * 64,
        )
        session.add(task)
        await session.flush()
        repository = ComparisonRepository(session)
        repository.add_event(
            comparison_id=task.id,
            stage=TaskStage.CREATED,
            event_type=TaskEventType.INFO,
            progress=0,
            message="脱敏事件。",
            details={"code": "CREATED"},
        )
        await session.flush()
        loaded = await repository.get_by_idempotency_hash("d" * 64)
        assert loaded is not None
        assert loaded.id == task.id
        assert len(loaded.events) == 1
        # 仓储没有提交；调用方 rollback 后任务和事件均不应持久化。
        await session.rollback()


def _service(
    session_factory: async_sessionmaker[AsyncSession],
) -> ComparisonApplicationService:
    """使用隔离会话工厂和本地 Fixture 组装真实 M1-B 服务。by AI.Coding"""
    # 集成测试只使用打包合成 Fixture，禁止引入真实淘宝网络调用。
    return ComparisonApplicationService(
        lambda: UnitOfWork(session_factory), FixtureCommerceDataProvider(Settings())
    )


@pytest.mark.integration
async def test_service_create_parse_confirm_and_idempotent_replay(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证草稿、解析、确认和同载荷幂等重放闭环。by AI.Coding"""
    service = _service(session_factory)
    command = CreateComparisonCommand(
        (
            "https://item.taobao.com/item.htm?id=10001",
            "https://item.taobao.com/item.htm?id=10002",
        ),
        30,
    )
    # 两次相同 key 与同载荷仅返回同一任务，候选和事件不会重复写入。
    created = await service.create_comparison(command, idempotency_key="m1b-test-key")
    replayed = await service.create_comparison(command, idempotency_key="m1b-test-key")
    assert replayed.id == created.id

    parsed = await service.parse_products(created.id)
    assert parsed.status == "awaiting_product_confirmation"
    assert all(product.latest_snapshot is not None for product in parsed.products)
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
    assert confirmed.status == "awaiting_dimension_confirmation"
    assert [product.selected_sku_id for product in confirmed.products] == [
        None if not product.skus else product.skus[0].id for product in parsed.products
    ]
