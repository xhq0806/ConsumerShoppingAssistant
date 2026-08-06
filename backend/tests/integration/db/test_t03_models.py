"""T03 PostgreSQL 关系、约束与迁移集成测试。by AI.Coding"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from conftest import migrated_postgres
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.domain.comparisons import TaskEventType, TaskStage
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.models import (
    ComparisonProduct,
    ComparisonTask,
    ProductSku,
    ProductSnapshot,
    TaskEvent,
)
from app.providers.commerce.dto import (
    NormalizedProductUrl,
    ProductDTO,
    SkuDTO,
    SourceReference,
)

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """使用共享隔离夹具启动 PostgreSQL 并迁移到 0002。by AI.Coding"""
    with migrated_postgres("0002") as database:
        engine = create_async_engine(database.async_url)
        yield async_sessionmaker(engine, expire_on_commit=False)
        await engine.dispose()
        command.downgrade(database.alembic_config, "0001")


def _source(source_id: str) -> SourceReference:
    """创建测试 DTO 的最小来源引用。by AI.Coding"""
    return SourceReference(provider="fixture", source_id=source_id, obtained_at=datetime.now(UTC))


def _product_dto(title: str, source_id: str) -> ProductDTO:
    """创建事实快照测试 DTO。by AI.Coding"""
    return ProductDTO(external_product_id=source_id, title=title, source=_source(source_id))


def _sku_dto(external_id: str, name: str) -> SkuDTO:
    """创建 SKU 测试 DTO。by AI.Coding"""
    return SkuDTO(external_sku_id=external_id, name=name)


async def _create_product(
    session: AsyncSession, task: ComparisonTask, *, position: int, external_id: str
) -> ComparisonProduct:
    """创建并 flush 一个规范化候选商品。by AI.Coding"""
    repository = ComparisonRepository(session)
    product = repository.add_candidate_from_dto(
        comparison_id=task.id,
        position=position,
        product_url=NormalizedProductUrl(
            canonical_url=f"https://item.taobao.com/item.htm?id={external_id}",
            host="item.taobao.com",
            external_product_id=external_id,
            safe_url_fingerprint=external_id.zfill(64),
        ),
    )
    session.add(product)
    await session.flush()
    return product


@pytest.mark.integration
async def test_multiple_snapshots_skus_and_private_cascade(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """同商品支持多快照、多 SKU，删除任务级联私有子图。by AI.Coding"""
    async with session_factory() as session, session.begin():
        task = ComparisonTask(review_window_days=30, progress=0)
        session.add(task)
        await session.flush()
        product = await _create_product(session, task, position=0, external_id="123")
        repository = ComparisonRepository(session)
        repository.add_snapshot_from_dto(
            comparison_product_id=product.id, product=_product_dto("快照一", "1")
        )
        repository.add_snapshot_from_dto(
            comparison_product_id=product.id, product=_product_dto("快照二", "2")
        )
        repository.add_sku_from_dto(comparison_product_id=product.id, sku=_sku_dto("sku-1", "黑色"))
        repository.add_sku_from_dto(comparison_product_id=product.id, sku=_sku_dto("sku-2", "白色"))
        session.add(
            TaskEvent(
                comparison_id=task.id,
                stage=TaskStage.CREATED,
                event_type=TaskEventType.INFO,
                details={},
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ProductSnapshot)
                .where(ProductSnapshot.comparison_product_id == product.id)
            )
            == 2
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ProductSku)
                .where(ProductSku.comparison_product_id == product.id)
            )
            == 2
        )
        await session.delete(task)
        await session.flush()
        assert await session.scalar(select(func.count()).select_from(ProductSku)) == 0
        assert await session.scalar(select(func.count()).select_from(ProductSnapshot)) == 0
        assert await session.scalar(select(func.count()).select_from(TaskEvent)) == 0


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["position", "sku", "external_product", "fingerprint"])
async def test_unique_constraints_reject_duplicates(
    session_factory: async_sessionmaker[AsyncSession], kind: str
) -> None:
    """数据库拒绝重复商品位置和重复 SKU 外部 ID。by AI.Coding"""
    async with session_factory() as session:
        task = ComparisonTask(review_window_days=30, progress=0)
        session.add(task)
        await session.flush()
        product = await _create_product(session, task, position=0, external_id="456")
        if kind in {"position", "external_product", "fingerprint"}:
            duplicate = ComparisonRepository(session).add_candidate_from_dto(
                comparison_id=task.id,
                position=0 if kind == "position" else 1,
                product_url=NormalizedProductUrl(
                    canonical_url=(
                        "https://item.taobao.com/item.htm?id=456"
                        if kind == "external_product"
                        else "https://item.taobao.com/item.htm?id=789"
                    ),
                    host="item.taobao.com",
                    external_product_id="456" if kind == "external_product" else "789",
                    safe_url_fingerprint="456".zfill(64) if kind == "fingerprint" else "b" * 64,
                ),
            )
            session.add(duplicate)
        else:
            repository = ComparisonRepository(session)
            repository.add_sku_from_dto(
                comparison_product_id=product.id, sku=_sku_dto("same", "一")
            )
            repository.add_sku_from_dto(
                comparison_product_id=product.id, sku=_sku_dto("same", "二")
            )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.integration
async def test_deleting_selected_sku_clears_selection(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """删除已选 SKU 只清空选择，不修改候选商品主键。by AI.Coding"""
    async with session_factory() as session, session.begin():
        task = ComparisonTask(review_window_days=30, progress=0)
        session.add(task)
        await session.flush()
        product = await _create_product(session, task, position=0, external_id="333")
        sku = ComparisonRepository(session).add_sku_from_dto(
            comparison_product_id=product.id, sku=_sku_dto("selected", "已选 SKU")
        )
        await session.flush()
        product.selected_sku_id = sku.id
        await session.flush()
        product_id = product.id

        await session.delete(sku)
        await session.flush()
        await session.refresh(product)

        assert product.id == product_id
        assert product.selected_sku_id is None


@pytest.mark.integration
async def test_deleting_task_with_selected_sku_cascades_aggregate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """删除含已选 SKU 的任务应成功级联整个 T03 私有聚合。by AI.Coding"""
    async with session_factory() as session, session.begin():
        task = ComparisonTask(review_window_days=30, progress=0)
        session.add(task)
        await session.flush()
        product = await _create_product(session, task, position=0, external_id="444")
        sku = ComparisonRepository(session).add_sku_from_dto(
            comparison_product_id=product.id, sku=_sku_dto("selected", "已选 SKU")
        )
        await session.flush()
        product.selected_sku_id = sku.id
        await session.flush()

        task_id = task.id
        product_id = product.id
        sku_id = sku.id
        await session.delete(task)
        await session.flush()
        session.expire_all()

        assert await session.get(ComparisonTask, task_id) is None
        assert await session.get(ComparisonProduct, product_id) is None
        assert await session.get(ProductSku, sku_id) is None


@pytest.mark.integration
async def test_selected_sku_must_belong_to_product(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """数据库保证 selected_sku_id 所指 SKU 属于对应商品。by AI.Coding"""
    async with session_factory() as session:
        task = ComparisonTask(review_window_days=60, progress=100)
        session.add(task)
        await session.flush()
        first = await _create_product(session, task, position=0, external_id="111")
        second = await _create_product(session, task, position=1, external_id="222")
        foreign_sku = ComparisonRepository(session).add_sku_from_dto(
            comparison_product_id=second.id, sku=_sku_dto("foreign", "其他商品 SKU")
        )
        await session.flush()
        first.selected_sku_id = foreign_sku.id
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
