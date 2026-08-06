"""T05 PostgreSQL 约束、删除与迁移集成测试。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from alembic.config import Config
from conftest import migrated_postgres
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.core.errors import InputError
from app.domain.dimensions import DimensionDomain, DimensionSourceType, DimensionValueType
from app.domain.reports import ReportClaimType, ReportStatus
from app.domain.reviews import ReviewSentiment
from app.infrastructure.db.analysis_repository import AnalysisRepository
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.models import (
    AnalysisMetric,
    ComparisonProduct,
    ComparisonReport,
    ComparisonTask,
    DimensionDefinition,
    ModelRun,
    RawReview,
    ReportClaim,
    ReviewAnnotation,
)
from app.providers.commerce.dto import NormalizedProductUrl, ReviewDTO, SourceReference
from app.providers.llm.audit import SQLAlchemyLLMAuditSink
from app.providers.llm.base import LLMAuditEvent, TokenUsage

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


def _dimension(code: str) -> DimensionDefinition:
    """创建满足目录约束的评论维度。by AI.Coding"""
    return DimensionDefinition(
        code=code,
        name=code,
        domain=DimensionDomain.REVIEW_EXPERIENCE,
        source_type=DimensionSourceType.REVIEW_METRIC,
        value_type=DimensionValueType.TEXT,
        default_priority=0,
        min_sample_size=0,
    )


async def _task_product_dimension(
    session: AsyncSession,
) -> tuple[ComparisonTask, ComparisonProduct, DimensionDefinition]:
    """创建 T05 测试所需任务、商品与共享维度。by AI.Coding"""
    task = ComparisonTask(review_window_days=30, progress=0)
    session.add(task)
    await session.flush()
    product = ComparisonRepository(session).add_candidate_from_dto(
        comparison_id=task.id,
        position=0,
        product_url=NormalizedProductUrl(
            canonical_url="https://item.taobao.com/item.htm?id=1",
            host="item.taobao.com",
            external_product_id="1",
            safe_url_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        ),
    )
    dimension = _dimension(f"dimension_{uuid.uuid4().hex}")
    session.add_all([product, dimension])
    await session.flush()
    return task, product, dimension


@pytest.mark.integration
async def test_migration_has_sixteen_tables_and_t05_varchar_checks(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """迁移创建恰好十六张业务表且枚举列为 VARCHAR。by AI.Coding"""
    _, _, async_url = migrated_database
    engine = create_async_engine(async_url)
    async with engine.connect() as connection:
        tables = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
        columns = await connection.run_sync(
            lambda conn: inspect(conn).get_columns("review_annotations")
        )
        checks = await connection.run_sync(
            lambda conn: inspect(conn).get_check_constraints("review_annotations")
        )
    await engine.dispose()
    assert tables - {"alembic_version"} == {
        "comparison_tasks",
        "comparison_products",
        "product_snapshots",
        "product_skus",
        "task_events",
        "brand_profiles",
        "brand_sources",
        "dimension_definitions",
        "task_dimensions",
        "raw_reviews",
        "review_annotations",
        "analysis_metrics",
        "comparison_reports",
        "report_claims",
        "followup_messages",
        "model_runs",
    }
    sentiment = next(column for column in columns if column["name"] == "sentiment")
    assert "VARCHAR" in str(sentiment["type"])
    assert any("sentiment" in str(check["sqltext"]) for check in checks)


@pytest.mark.integration
async def test_review_uniqueness_annotation_dimension_and_model_set_null(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """评论与注解唯一，维度受保护，模型运行删除时注解置空。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        task, product, dimension = await _task_product_dimension(session)
        review = AnalysisRepository(session).add_review_from_dto(
            comparison_product_id=product.id,
            review=ReviewDTO(
                external_review_id="review-1",
                created_at=datetime.now(UTC),
                content="续航很好",
                rating=5,
                source=SourceReference(
                    provider="fixture", source_id="review-1", obtained_at=datetime.now(UTC)
                ),
            ),
        )
        run = ModelRun(
            event_id=uuid.uuid4(),
            comparison_id=task.id,
            purpose="annotation",
            provider="fake",
            model="fake-model",
            trace_id="trace",
            prompt_version="v1",
            status="success",
            latency_ms=1,
            attempts=1,
            occurred_at=datetime.now(UTC),
        )
        session.add_all([review, run])
        await session.flush()
        annotation = ReviewAnnotation(
            review_id=review.id,
            dimension_id=dimension.id,
            sentiment=ReviewSentiment.POSITIVE,
            confidence=0.9,
            evidence="很好",
            model_run_id=run.id,
        )
        session.add(annotation)
        await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                AnalysisRepository(session).add_review_from_dto(
                    comparison_product_id=product.id,
                    review=ReviewDTO(
                        external_review_id="review-1",
                        created_at=datetime.now(UTC),
                        content="重复",
                        rating=4,
                        source=SourceReference(
                            provider="fixture",
                            source_id="review-1-duplicate",
                            obtained_at=datetime.now(UTC),
                        ),
                    ),
                )
                await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    ReviewAnnotation(
                        review_id=review.id,
                        dimension_id=dimension.id,
                        sentiment=ReviewSentiment.NEUTRAL,
                        confidence=0.5,
                        evidence="续航",
                    )
                )
                await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.delete(dimension)
                await session.flush()
        await session.delete(run)
        await session.flush()
        await session.refresh(annotation)
        assert annotation.model_run_id is None
        await session.rollback()


@pytest.mark.integration
async def test_raw_review_dto_mapping_preserves_source_and_ingestion_time(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """评论映射仅保留白名单来源、采集时间和独立入库时间。by AI.Coding"""
    session_factory, _, _ = migrated_database
    obtained_at = datetime.now(UTC)
    async with session_factory() as session:
        _, product, _ = await _task_product_dimension(session)
        review = AnalysisRepository(session).add_review_from_dto(
            comparison_product_id=product.id,
            review=ReviewDTO(
                external_review_id="trace-review",
                created_at=obtained_at,
                content="可追溯评论",
                source=SourceReference(
                    provider="fixture", source_id="review-source-1", obtained_at=obtained_at
                ),
            ),
        )
        session.add(review)
        await session.flush()
        assert review.source == {
            "provider": "fixture",
            "source_id": "review-source-1",
            "obtained_at": obtained_at.isoformat(),
        }
        assert review.fetched_at == obtained_at
        assert review.ingested_at is not None
        assert "raw_payload" not in RawReview.__table__.columns
        await session.rollback()


async def test_raw_review_source_rejects_extra_keys_at_orm_and_database(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """RawReview source 在 ORM 与 DB 两层都只允许三个白名单键。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        _, product, _ = await _task_product_dimension(session)
        review = AnalysisRepository(session).add_review_from_dto(
            comparison_product_id=product.id,
            review=ReviewDTO(
                external_review_id="blocked",
                created_at=datetime.now(UTC),
                content="正文",
                source=SourceReference(
                    provider="fixture", source_id="blocked", obtained_at=datetime.now(UTC)
                ),
            ),
        )
        with pytest.raises(InputError, match="只能包含"):
            review.source = {
                "provider": "fixture",
                "source_id": "blocked",
                "obtained_at": datetime.now(UTC).isoformat(),
                "cookie": "secret",
            }
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO raw_reviews "
                    "(id,comparison_product_id,external_review_id,reviewed_at,content,content_hash,"
                    "source,fetched_at,ingested_at) VALUES "
                    "(gen_random_uuid(),:product_id,'raw-extra',now(),'正文',:hash,"
                    "CAST(:source AS jsonb),now(),now())"
                ),
                {
                    "product_id": product.id,
                    "hash": "b" * 64,
                    "source": '{"provider":"fixture","source_id":"x",'
                    '"obtained_at":"2026-01-01T00:00:00+00:00","cookie":"secret"}',
                },
            )
        await session.rollback()


@pytest.mark.integration
async def test_metric_scope_uniqueness_and_product_belongs_to_task(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """任务级空商品口径不重复且商品级指标不能跨任务挂接。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        task, product, dimension = await _task_product_dimension(session)
        session.add(
            AnalysisMetric(
                comparison_id=task.id,
                dimension_id=dimension.id,
                metric_type="positive_ratio",
                numeric_value=0.5,
                sample_size=2,
                confidence=0.8,
                source_refs=[{"kind": "review", "id": "review-input-1"}],
            )
        )
        await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    AnalysisMetric(
                        comparison_id=task.id,
                        dimension_id=dimension.id,
                        metric_type="positive_ratio",
                        text_value="duplicate",
                        sample_size=2,
                        source_refs=[{"kind": "review", "id": "review-input-2"}],
                    )
                )
                await session.flush()
        other_task = ComparisonTask(review_window_days=30, progress=0)
        session.add(other_task)
        await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    AnalysisMetric(
                        comparison_id=other_task.id,
                        comparison_product_id=product.id,
                        dimension_id=dimension.id,
                        metric_type="sample",
                        numeric_value=1,
                        sample_size=1,
                        source_refs=[{"kind": "review", "id": "review-input-3"}],
                    )
                )
                await session.flush()
        await session.rollback()


@pytest.mark.integration
async def test_database_rejects_empty_metric_sources_and_zero_attempts(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """数据库拒绝不可复算指标和未实际调用的模型运行。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        task, _, dimension = await _task_product_dimension(session)
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO analysis_metrics "
                    "(id,comparison_id,dimension_id,metric_type,numeric_value,sample_size,"
                    "source_refs,calculated_at) VALUES "
                    "(gen_random_uuid(),:task_id,:dimension_id,'invalid',1,0,'[]'::jsonb,now())"
                ),
                {"task_id": task.id, "dimension_id": dimension.id},
            )
        await session.rollback()
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO model_runs "
                    "(id,event_id,purpose,provider,model,trace_id,prompt_version,status,"
                    "latency_ms,attempts,occurred_at) VALUES "
                    "(gen_random_uuid(),gen_random_uuid(),'x','fake','m','t','v1',"
                    "'success',0,0,now())"
                )
            )
        await session.rollback()


@pytest.mark.integration
async def test_report_claim_cascade_task_private_graph_and_catalog_retention(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """报告删 claim，任务删私有子图，但共享维度保留。by AI.Coding"""
    session_factory, _, _ = migrated_database
    async with session_factory() as session:
        task, product, dimension = await _task_product_dimension(session)
        report = ComparisonReport(comparison_id=task.id, version=1, status=ReportStatus.DRAFT)
        session.add(report)
        await session.flush()
        session.add(
            ReportClaim(
                report_id=report.id,
                claim_type=ReportClaimType.FACT,
                text="有依据",
                source_refs=[{"type": "analysis_metric", "id": str(uuid.uuid4())}],
                display_order=0,
            )
        )
        AnalysisRepository(session).add_review_from_dto(
            comparison_product_id=product.id,
            review=ReviewDTO(
                external_review_id="delete-review",
                created_at=datetime.now(UTC),
                content="正文",
                source=SourceReference(
                    provider="fixture",
                    source_id="delete-review",
                    obtained_at=datetime.now(UTC),
                ),
            ),
        )
        await session.flush()
        await session.delete(report)
        await session.flush()
        assert await session.scalar(select(func.count()).select_from(ReportClaim)) == 0
        await session.delete(task)
        await session.flush()
        assert await session.scalar(select(func.count()).select_from(RawReview)) == 0
        assert await session.get(DimensionDefinition, dimension.id) is not None
        await session.rollback()


@pytest.mark.integration
async def test_sqlalchemy_audit_sink_whitelists_metadata_and_does_not_commit(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """审计 sink 仅落安全元数据并由调用方控制提交。by AI.Coding"""
    session_factory, _, _ = migrated_database
    event_id = uuid.uuid4()
    event = LLMAuditEvent.now(
        event_id=event_id,
        purpose="report",
        provider="fake",
        model="fake-model",
        trace_id="trace-safe",
        prompt_version="v1",
        status="success",
        latency_ms=3,
        attempts=1,
        usage=TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5),
    )
    async with session_factory() as session:
        await SQLAlchemyLLMAuditSink(session).record(event)
        run = await session.scalar(select(ModelRun).where(ModelRun.event_id == event_id))
        assert run is not None and run.total_tokens == 5
        assert "prompt" not in set(ModelRun.__table__.columns) - {"prompt_version"}
        await session.rollback()
    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(ModelRun).where(ModelRun.event_id == event_id)
            )
            == 0
        )


@pytest.mark.integration
async def test_raw_sql_checks_and_0004_downgrade_reupgrade(
    migrated_database: tuple[async_sessionmaker[AsyncSession], Config, str],
) -> None:
    """数据库拒绝非法边界且 0004 可降级重升。by AI.Coding"""
    session_factory, config, async_url = migrated_database
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO model_runs "
                    "(id,event_id,purpose,provider,model,trace_id,prompt_version,status,"
                    "latency_ms,attempts,occurred_at) VALUES "
                    "(gen_random_uuid(),gen_random_uuid(),'x','fake','m','t','v1',"
                    "'success',-1,1,now())"
                )
            )
        await session.rollback()
    command.downgrade(config, "0003")
    engine = create_async_engine(async_url)
    async with engine.connect() as connection:
        remaining = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
    await engine.dispose()
    assert "dimension_definitions" in remaining
    assert "model_runs" not in remaining
    command.upgrade(config, "0004")
