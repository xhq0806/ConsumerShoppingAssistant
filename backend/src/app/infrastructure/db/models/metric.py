"""T05 确定性分析指标 ORM。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.domain.dimensions import validate_non_negative
from app.domain.metrics import validate_metric_source_refs
from app.domain.reviews import validate_confidence
from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.comparison import ComparisonProduct, ComparisonTask
    from app.infrastructure.db.models.dimension import DimensionDefinition


class AnalysisMetric(Base):
    """保存可复算且不依赖 LLM 作为统计真源的指标。by AI.Coding"""

    __tablename__ = "analysis_metrics"
    __table_args__ = (
        CheckConstraint("numeric_value IS NOT NULL OR text_value IS NOT NULL", name="has_value"),
        CheckConstraint("sample_size >= 0", name="sample_size"),
        CheckConstraint("jsonb_typeof(source_refs) = 'array'", name="source_refs_array"),
        CheckConstraint("jsonb_array_length(source_refs) > 0", name="source_refs_nonempty"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence"),
        ForeignKeyConstraint(
            ["comparison_id", "comparison_product_id"],
            ["comparison_products.comparison_id", "comparison_products.id"],
            name="fk_analysis_metrics_product_belongs_to_task",
            ondelete="CASCADE",
        ),
        Index(
            "uq_analysis_metrics_scope",
            "comparison_id",
            "comparison_product_id",
            "dimension_id",
            "metric_type",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_analysis_metrics_comparison_dimension", "comparison_id", "dimension_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    comparison_product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dimension_definitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    text_value: Mapped[str | None] = mapped_column(Text)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    comparison: Mapped[ComparisonTask] = relationship(
        back_populates="analysis_metrics", overlaps="analysis_metrics,comparison_product"
    )
    comparison_product: Mapped[ComparisonProduct | None] = relationship(
        back_populates="analysis_metrics", overlaps="analysis_metrics,comparison"
    )
    dimension: Mapped[DimensionDefinition] = relationship(back_populates="analysis_metrics")

    @validates("source_refs")
    def _validate_source_refs(self, _key: str, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """在 ORM 赋值边界拒绝无输入来源的可复算指标。by AI.Coding"""
        return validate_metric_source_refs(value)

    @validates("sample_size")
    def _validate_sample_size(self, _key: str, value: int) -> int:
        """在 ORM 赋值边界拒绝负样本量。by AI.Coding"""
        return validate_non_negative(value, field_name="样本量")

    @validates("confidence")
    def _validate_confidence(self, _key: str, value: float | None) -> float | None:
        """在 ORM 赋值边界复用可空置信度校验。by AI.Coding"""
        return validate_confidence(value)
