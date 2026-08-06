"""T05 ORM metadata、枚举存储与安全列测试。by AI.Coding"""

from sqlalchemy import Enum
from sqlalchemy.sql.sqltypes import Enum as SqlEnum

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (
    AnalysisMetric,
    ComparisonReport,
    FollowupMessage,
    ModelRun,
    RawReview,
    ReportClaim,
    ReviewAnnotation,
)


def test_metadata_registers_exactly_sixteen_business_tables() -> None:
    """公共 metadata 应注册本期恰好十六张业务表。by AI.Coding"""
    assert set(Base.metadata.tables) == {
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


def test_all_t05_enum_columns_use_varchar_without_native_enum() -> None:
    """T05 枚举列必须落为 VARCHAR 并配合显式 CHECK。by AI.Coding"""
    columns = [
        ReviewAnnotation.__table__.c.sentiment,
        ComparisonReport.__table__.c.status,
        ReportClaim.__table__.c.claim_type,
        FollowupMessage.__table__.c.role,
        ModelRun.__table__.c.status,
    ]
    assert all(isinstance(column.type, Enum) for column in columns)
    assert all(
        column.type.native_enum is False for column in columns if isinstance(column.type, SqlEnum)
    )
    assert all(
        column.type.create_constraint is False
        for column in columns
        if isinstance(column.type, SqlEnum)
    )


def test_raw_review_and_metric_keep_recalculation_trace_fields() -> None:
    """评论保留来源与双时间，指标来源引用为必填 JSON 数组。by AI.Coding"""
    assert {"source", "fetched_at", "ingested_at"} <= set(RawReview.__table__.columns.keys())
    assert AnalysisMetric.__table__.c.source_refs.nullable is False


def test_model_runs_contains_only_audit_metadata_columns() -> None:
    """模型运行表不得出现提示词、消息、评论、响应或密钥正文列。by AI.Coding"""
    names = set(ModelRun.__table__.columns.keys())
    assert {"event_id", "purpose", "provider", "model", "trace_id", "prompt_version"} <= names
    forbidden_fragments = {"prompt", "message", "review", "response", "secret", "api_key", "cookie"}
    assert not {
        name
        for name in names
        for fragment in forbidden_fragments
        if fragment in name and name != "prompt_version"
    }
