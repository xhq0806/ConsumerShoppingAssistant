"""T04 维度目录与任务维度 ORM。by AI.Coding"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.domain.dimensions import (
    DimensionDomain,
    DimensionSourceType,
    DimensionValueType,
    DimensionVisualization,
    MissingDataPolicy,
    normalize_dimension_code,
    validate_non_negative,
    validate_task_dimension_position,
)
from app.infrastructure.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.comparison import ComparisonTask
    from app.infrastructure.db.models.metric import AnalysisMetric
    from app.infrastructure.db.models.review import ReviewAnnotation


class DimensionDefinition(TimestampMixin, Base):
    """保存可由后续用例引用的共享受控维度定义。by AI.Coding"""

    __tablename__ = "dimension_definitions"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('product_fact', 'brand_background', 'category_specification', "
            "'review_experience', 'user_preference')",
            name="domain",
        ),
        CheckConstraint(
            "source_type IN ('product_fact', 'brand_fact', 'review_metric', "
            "'derived_metric', 'user_preference')",
            name="source_type",
        ),
        CheckConstraint(
            "value_type IN ('text', 'integer', 'decimal', 'boolean', 'percentage', "
            "'currency', 'rating')",
            name="value_type",
        ),
        CheckConstraint(
            "visualization IN ('text', 'table', 'bar', 'radar', 'trend', 'distribution')",
            name="visualization",
        ),
        CheckConstraint(
            "missing_data_policy IN ('show_unknown', 'exclude_from_scoring', 'lower_confidence')",
            name="missing_data_policy",
        ),
        CheckConstraint("jsonb_typeof(config) = 'object'", name="config_object"),
        CheckConstraint("default_priority >= 0", name="default_priority"),
        CheckConstraint("min_sample_size >= 0", name="min_sample_size"),
        CheckConstraint(
            "NOT (code = 'brand_founded_year' AND affects_recommendation)",
            name="founded_year_not_scored",
        ),
        Index("ix_dimension_definitions_category_enabled", "category", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[DimensionDomain] = mapped_column(
        Enum(
            DimensionDomain,
            native_enum=False,
            create_constraint=False,
            length=22,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    source_type: Mapped[DimensionSourceType] = mapped_column(
        Enum(
            DimensionSourceType,
            native_enum=False,
            create_constraint=False,
            length=15,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    value_type: Mapped[DimensionValueType] = mapped_column(
        Enum(
            DimensionValueType,
            native_enum=False,
            create_constraint=False,
            length=10,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    config: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    default_priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rankable: Mapped[bool] = mapped_column(default=True, nullable=False)
    affects_recommendation: Mapped[bool] = mapped_column(default=True, nullable=False)
    min_sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_data_policy: Mapped[MissingDataPolicy] = mapped_column(
        Enum(
            MissingDataPolicy,
            native_enum=False,
            create_constraint=False,
            length=20,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=MissingDataPolicy.SHOW_UNKNOWN,
        nullable=False,
    )
    visualization: Mapped[DimensionVisualization] = mapped_column(
        Enum(
            DimensionVisualization,
            native_enum=False,
            create_constraint=False,
            length=12,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=DimensionVisualization.TEXT,
        nullable=False,
    )
    user_removable: Mapped[bool] = mapped_column(default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    task_dimensions: Mapped[list[TaskDimension]] = relationship(back_populates="dimension")
    review_annotations: Mapped[list[ReviewAnnotation]] = relationship(
        back_populates="dimension", passive_deletes=True
    )
    analysis_metrics: Mapped[list[AnalysisMetric]] = relationship(
        back_populates="dimension", passive_deletes=True
    )

    @validates("code")
    def _validate_code(self, _key: str, value: str) -> str:
        """稳定化维度 code，并默认关闭成立年份的推荐影响。by AI.Coding"""
        normalized = normalize_dimension_code(value)
        # 成立年份是展示信息；ORM 默认值与数据库强制约束保持一致。
        if normalized == "brand_founded_year":
            self.affects_recommendation = False
        return normalized

    @validates("default_priority", "min_sample_size")
    def _validate_non_negative(self, key: str, value: int) -> int:
        """在 ORM 赋值边界拒绝负优先级和负样本阈值。by AI.Coding"""
        return validate_non_negative(value, field_name=key)


class TaskDimension(Base):
    """保存任务对共享维度目录的选择和排序。by AI.Coding"""

    __tablename__ = "task_dimensions"
    __table_args__ = (
        UniqueConstraint(
            "comparison_id", "dimension_id", name="uq_task_dimensions_comparison_dimension"
        ),
        CheckConstraint(
            "(selected AND position IS NOT NULL AND position >= 0) OR "
            "(NOT selected AND position IS NULL)",
            name="selected_position",
        ),
        Index(
            "uq_task_dimensions_selected_position",
            "comparison_id",
            "position",
            unique=True,
            postgresql_where=text("selected AND position IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dimension_definitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position: Mapped[int | None] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(default=True, nullable=False)
    user_selected: Mapped[bool] = mapped_column(default=False, nullable=False)
    selection_reason: Mapped[str | None] = mapped_column(Text)

    comparison: Mapped[ComparisonTask] = relationship(back_populates="dimensions")
    dimension: Mapped[DimensionDefinition] = relationship(back_populates="task_dimensions")

    @validates("position")
    def _validate_position(self, _key: str, value: int | None) -> int | None:
        """校验当前选中状态下的维度位置。by AI.Coding"""
        selected = self.__dict__.get("selected", True)
        return validate_task_dimension_position(selected=selected, position=value)
