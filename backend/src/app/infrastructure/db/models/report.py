"""T05 版本报告、结论与受限追问 ORM。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.domain.reports import (
    FollowupRole,
    ReportClaimType,
    ReportStatus,
    validate_claim_source_refs,
    validate_report_version,
)
from app.domain.reviews import validate_confidence
from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.comparison import ComparisonTask


class ComparisonReport(Base):
    """保存任务下可追溯的版本化结构化报告。by AI.Coding"""

    __tablename__ = "comparison_reports"
    __table_args__ = (
        UniqueConstraint("comparison_id", "version", name="uq_comparison_reports_task_version"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(
            "status IN ('draft', 'generating', 'completed', 'partial', 'failed')", name="status"
        ),
        Index("ix_comparison_reports_comparison_generated", "comparison_id", "generated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(
            ReportStatus,
            native_enum=False,
            create_constraint=False,
            length=10,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=ReportStatus.DRAFT,
        nullable=False,
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    differences: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    full_comparison: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    comparison: Mapped[ComparisonTask] = relationship(back_populates="reports")
    claims: Mapped[list[ReportClaim]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("version")
    def _validate_version(self, _key: str, value: int) -> int:
        """在 ORM 赋值边界复用报告版本纯校验。by AI.Coding"""
        return validate_report_version(value)


class ReportClaim(Base):
    """保存报告结论及其至少一个结构化来源引用。by AI.Coding"""

    __tablename__ = "report_claims"
    __table_args__ = (
        CheckConstraint(
            "claim_type IN ('fact', 'advantage', 'disadvantage', 'recommendation', 'warning')",
            name="claim_type",
        ),
        CheckConstraint("jsonb_typeof(source_refs) = 'array'", name="source_refs_array"),
        CheckConstraint("jsonb_array_length(source_refs) > 0", name="source_refs_nonempty"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence"),
        CheckConstraint("display_order >= 0", name="display_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_type: Mapped[ReportClaimType] = mapped_column(
        Enum(
            ReportClaimType,
            native_enum=False,
            create_constraint=False,
            length=14,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    report: Mapped[ComparisonReport] = relationship(back_populates="claims")

    @validates("source_refs")
    def _validate_source_refs(self, _key: str, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """在 ORM 赋值边界拒绝无来源或空来源结论。by AI.Coding"""
        return validate_claim_source_refs(value)

    @validates("confidence")
    def _validate_confidence(self, _key: str, value: float | None) -> float | None:
        """在 ORM 赋值边界复用可空置信度校验。by AI.Coding"""
        return validate_confidence(value)


class FollowupMessage(Base):
    """保存任务内受限追问历史而不承担模型长期记忆。by AI.Coding"""

    __tablename__ = "followup_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        Index("ix_followup_messages_comparison_created", "comparison_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[FollowupRole] = mapped_column(
        Enum(
            FollowupRole,
            native_enum=False,
            create_constraint=False,
            length=9,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    answer_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    comparison: Mapped[ComparisonTask] = relationship(back_populates="followup_messages")
