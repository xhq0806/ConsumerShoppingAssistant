"""T05 供应商中立模型运行审计 ORM。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.domain.model_runs import ModelRunStatus, validate_attempts, validate_non_negative_count
from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.comparison import ComparisonTask
    from app.infrastructure.db.models.review import ReviewAnnotation


class ModelRun(Base):
    """仅保存 LLM 审计安全元数据，绝不保存调用正文或凭据。by AI.Coding"""

    __tablename__ = "model_runs"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_model_runs_event_id"),
        CheckConstraint("status IN ('success', 'error')", name="status"),
        CheckConstraint("latency_ms >= 0", name="latency_ms"),
        CheckConstraint("attempts >= 1", name="attempts"),
        CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="input_tokens"),
        CheckConstraint("output_tokens IS NULL OR output_tokens >= 0", name="output_tokens"),
        CheckConstraint("total_tokens IS NULL OR total_tokens >= 0", name="total_tokens"),
        Index("ix_model_runs_purpose_status_created", "purpose", "status", "occurred_at"),
        Index("ix_model_runs_comparison_occurred", "comparison_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comparison_tasks.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ModelRunStatus] = mapped_column(
        Enum(
            ModelRunStatus,
            native_enum=False,
            create_constraint=False,
            length=7,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    comparison: Mapped[ComparisonTask | None] = relationship(back_populates="model_runs")
    annotations: Mapped[list[ReviewAnnotation]] = relationship(back_populates="model_run")

    @validates("attempts")
    def _validate_attempts(self, _key: str, value: int) -> int:
        """在 ORM 赋值边界确保首次 Gateway 调用计为一次。by AI.Coding"""
        return validate_attempts(value)

    @validates("latency_ms", "input_tokens", "output_tokens", "total_tokens")
    def _validate_non_negative(self, key: str, value: int | None) -> int | None:
        """在 ORM 赋值边界拒绝负审计计数。by AI.Coding"""
        return validate_non_negative_count(value, field_name=key)
