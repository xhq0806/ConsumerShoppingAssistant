"""T04 PostgreSQL 目录关系、约束与迁移集成测试。by AI.Coding"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from alembic.config import Config
from conftest import migrated_postgres
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.core.errors import DomainConflictError
from app.domain.brands import BrandField, BrandSourceType
from app.domain.dimensions import (
    DimensionDomain,
    DimensionSourceType,
    DimensionValueType,
    DimensionVisualization,
)
from app.infrastructure.db.catalog_repository import CatalogRepository
from app.infrastructure.db.models import (
    BrandProfile,
    BrandSource,
    ComparisonTask,
    DimensionDefinition,
    TaskDimension,
)

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def migrated_database() -> AsyncIterator[
    tuple[async_sessionmaker[AsyncSession], Config, str]
]:
    """使用共享隔离夹具启动 PostgreSQL 并迁移到当前 head。by AI.Coding"""
    with migrated_postgres("head") as database:
        engine = create_async_engine(database.async_url)
        yield (
            async_sessionmaker(engine, expire_on_commit=False),
            database.alembic_config,
            database.async_url,
        )
        await engine.dispose()
        command.downgrade(database.alembic_config, "0001")


def _dimension(*, code: str, source_type: DimensionSourceType) -> DimensionDefinition:
    """创建满足 T04 受控字段的维度定义。by AI.Coding"""
    return DimensionDefinition(
        code=code,
        name=code,
        domain=DimensionDomain.PRODUCT_FACT,
        source_type=source_type,
        value_type=DimensionValueType.TEXT,
        default_priority=0,
        min_sample_size=0,
        visualization=DimensionVisualization.TEXT,
    )


@pytest.mark.integration
async def test_conflicting_brand_sources_are_persisted_and_brand_delete_cascades(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """字段冲突来源可并存，删除品牌级联删除其来源。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session, session.begin():
        brand = BrandProfile.create(display_name="ACME")
        session.add(brand)
        await session.flush()
        session.add_all(
            [
                BrandSource(
                    brand_id=brand.id,
                    field_name=BrandField.FOUNDED_YEAR,
                    source_type=BrandSourceType.OFFICIAL_WEBSITE,
                    source_name="官网",
                    source_identifier="official",
                    value=1998,
                    confidence=1.0,
                ),
                BrandSource(
                    brand_id=brand.id,
                    field_name=BrandField.FOUNDED_YEAR,
                    source_type=BrandSourceType.TRUSTED_KNOWLEDGE_BASE,
                    source_name="知识库",
                    source_identifier="kb",
                    value=2001,
                    confidence=0.8,
                ),
            ]
        )
        await session.flush()
        assert await session.scalar(select(func.count()).select_from(BrandSource)) == 2
        await session.delete(brand)
        await session.flush()
        assert await session.scalar(select(func.count()).select_from(BrandSource)) == 0


@pytest.mark.integration
async def test_catalog_repository_flushes_without_commit(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """目录仓储可查询和 flush，但事务提交仍由调用方控制。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as first_session:
        repository = CatalogRepository(first_session)
        repository.add_brand(BrandProfile.create(display_name="Rollback Brand"))
        await repository.flush()
        assert await repository.get_brand_by_name("rollback-brand") is not None
        await first_session.rollback()
    async with session_factory() as second_session:
        assert (
            await second_session.scalar(
                select(func.count())
                .select_from(BrandProfile)
                .where(BrandProfile.normalized_name == "rollback brand")
            )
            == 0
        )


@pytest.mark.integration
async def test_catalog_resolves_only_enabled_registered_dimensions(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """目录仓储拒绝未知或 disabled code，只返回启用记录。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        enabled = _dimension(code="enabled_dimension", source_type=DimensionSourceType.PRODUCT_FACT)
        disabled = _dimension(
            code="disabled_dimension", source_type=DimensionSourceType.PRODUCT_FACT
        )
        disabled.enabled = False
        session.add_all([enabled, disabled])
        await session.flush()
        repository = CatalogRepository(session)
        assert await repository.resolve_enabled_dimension("enabled-dimension") is enabled
        with pytest.raises(DomainConflictError, match="停用"):
            await repository.resolve_enabled_dimension("disabled_dimension")
        with pytest.raises(DomainConflictError, match="未注册"):
            await repository.resolve_enabled_dimension("missing_dimension")
        await session.rollback()


@pytest.mark.integration
async def test_dimension_source_types_and_unique_codes(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """五种来源均可保存且重复 code 被拒绝。by AI.Coding"""
    session_factory, _, _ = migrated_database
    source_codes = [f"source_{index}" for index, _ in enumerate(DimensionSourceType)]
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                _dimension(code=code, source_type=source_type)
                for code, source_type in zip(source_codes, DimensionSourceType, strict=True)
            ]
        )
        await session.flush()
        assert (
            await session.scalar(
                select(func.count())
                .select_from(DimensionDefinition)
                .where(DimensionDefinition.code.in_(source_codes))
            )
            == 5
        )
    async with session_factory() as session:
        session.add_all(
            [
                _dimension(code="duplicate_code", source_type=DimensionSourceType.PRODUCT_FACT),
                _dimension(code="duplicate_code", source_type=DimensionSourceType.USER_PREFERENCE),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.integration
@pytest.mark.parametrize("column", ["default_priority", "min_sample_size"])
async def test_dimension_non_negative_checks_reject_raw_sql(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str], column: str
) -> None:
    """数据库拒绝绕过 ORM 写入负优先级或负样本阈值。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        statement = text(
            "INSERT INTO dimension_definitions "
            "(id, code, name, domain, source_type, value_type, config, default_priority, rankable, "
            "affects_recommendation, min_sample_size, missing_data_policy, "
            "visualization, user_removable, enabled, created_at, updated_at) VALUES "
            "(gen_random_uuid(), :code, 'raw', 'product_fact', 'product_fact', 'text', "
            "'{}'::jsonb, :priority, true, true, :sample, 'show_unknown', 'text', true, true, "
            "now(), now())"
        )
        with pytest.raises(IntegrityError):
            await session.execute(
                statement,
                {
                    "code": f"negative_{column}",
                    "priority": -1 if column == "default_priority" else 0,
                    "sample": -1 if column == "min_sample_size" else 0,
                },
            )
        await session.rollback()


@pytest.mark.integration
async def test_task_dimension_uniqueness_cascade_and_dimension_restrict(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """任务维度防重复，任务删除级联，维度被引用时限制删除。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        task = ComparisonTask(review_window_days=30, progress=0)
        first = _dimension(code="first_dimension", source_type=DimensionSourceType.PRODUCT_FACT)
        second = _dimension(
            code="second_dimension", source_type=DimensionSourceType.USER_PREFERENCE
        )
        session.add_all([task, first, second])
        await session.flush()
        session.add_all(
            [
                TaskDimension(
                    comparison_id=task.id, dimension_id=first.id, position=0, selected=True
                ),
                TaskDimension(
                    comparison_id=task.id, dimension_id=second.id, position=1, selected=True
                ),
            ]
        )
        await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    TaskDimension(
                        comparison_id=task.id,
                        dimension_id=first.id,
                        position=2,
                        selected=True,
                    )
                )
                await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    text(
                        "INSERT INTO task_dimensions "
                        "(id, comparison_id, dimension_id, position, selected, user_selected) "
                        "VALUES (gen_random_uuid(), :task_id, :dimension_id, 0, true, false)"
                    ),
                    {"task_id": task.id, "dimension_id": second.id},
                )
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.delete(first)
                await session.flush()
        await session.delete(task)
        await session.flush()
        assert await session.scalar(select(func.count()).select_from(TaskDimension)) == 0
        assert await session.get(DimensionDefinition, first.id) is not None
        assert await session.get(DimensionDefinition, second.id) is not None
        await session.rollback()


@pytest.mark.integration
async def test_founded_year_dimension_defaults_to_display_only(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """品牌成立年份维度默认不影响推荐。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        seeded = await session.scalar(
            select(DimensionDefinition).where(DimensionDefinition.code == "brand_founded_year")
        )
        assert seeded is not None
        assert seeded.affects_recommendation is False
        dimension = DimensionDefinition(
            code="brand_founded_year",
            name="成立年份",
            domain=DimensionDomain.BRAND_BACKGROUND,
            source_type=DimensionSourceType.BRAND_FACT,
            value_type=DimensionValueType.INTEGER,
            default_priority=0,
            min_sample_size=0,
        )
        assert dimension.affects_recommendation is False


@pytest.mark.integration
async def test_founded_year_dimension_is_display_only_at_database_boundary(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """数据库也拒绝成立年份维度参与推荐。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "UPDATE dimension_definitions SET affects_recommendation = true "
                    "WHERE code = 'brand_founded_year'"
                )
            )
        await session.rollback()


@pytest.mark.integration
async def test_0003_downgrade_and_reupgrade(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """0003 可降至 0002 并重新升级，且 T03 表保持存在。by AI.Coding"""
    _, config, async_url = migrated_database
    command.downgrade(config, "0002")
    engine = create_async_engine(async_url)
    async with engine.connect() as connection:
        remaining = set(
            await connection.run_sync(
                lambda sync_connection: (
                    __import__("sqlalchemy").inspect(sync_connection).get_table_names()
                )
            )
        )
    await engine.dispose()
    assert "comparison_tasks" in remaining
    assert "brand_profiles" not in remaining
    command.upgrade(config, "0003")
