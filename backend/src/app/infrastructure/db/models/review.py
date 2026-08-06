"""T05 原始评论与多主题注解 ORM。by AI.Coding"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.domain.products import source_reference_payload, validate_source_reference_payload
from app.domain.reviews import ReviewSentiment, validate_confidence, validate_rating
from app.infrastructure.db.base import Base
from app.infrastructure.db.models._dto_construction import (
    dto_construction_token,
    require_dto_construction_token,
)
from app.providers.commerce.dto import ReviewDTO

if TYPE_CHECKING:
    from app.infrastructure.db.models.comparison import ComparisonProduct
    from app.infrastructure.db.models.dimension import DimensionDefinition
    from app.infrastructure.db.models.model_run import ModelRun


class RawReview(Base):
    """保存外部评论的最小必要字段。by AI.Coding"""

    __tablename__ = "raw_reviews"
    __table_args__ = (
        UniqueConstraint(
            "comparison_product_id",
            "external_review_id",
            name="uq_raw_reviews_product_external_id",
        ),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating"),
        CheckConstraint(
            "jsonb_typeof(source) = 'object' AND source ? 'provider' "
            "AND source ? 'source_id' AND source ? 'obtained_at' "
            "AND jsonb_typeof(source -> 'provider') = 'string' "
            "AND jsonb_typeof(source -> 'source_id') = 'string' "
            "AND jsonb_typeof(source -> 'obtained_at') = 'string' "
            "AND source - ARRAY['provider', 'source_id', 'obtained_at'] = '{}'::jsonb",
            name="source_reference",
        ),
        Index("ix_raw_reviews_content_hash", "content_hash"),
        Index("ix_raw_reviews_fetched_at", "fetched_at"),
        Index("ix_raw_reviews_ingested_at", "ingested_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_review_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    sku_text: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    comparison_product: Mapped[ComparisonProduct] = relationship(back_populates="raw_reviews")
    annotations: Mapped[list[ReviewAnnotation]] = relationship(
        back_populates="review", cascade="all, delete-orphan", passive_deletes=True
    )

    def __init__(self, *, _construction_token: object | None = None, **values: object) -> None:
        """拒绝绕过 ReviewDTO 最小字段白名单的普通 Python 直接构造。by AI.Coding"""
        require_dto_construction_token(_construction_token)
        for key, value in values.items():
            setattr(self, key, value)

    @classmethod
    def _from_dto(cls, *, comparison_product_id: uuid.UUID, review: ReviewDTO) -> RawReview:
        """从不可变评论 DTO 映射最小白名单字段。by AI.Coding"""
        # 内容哈希只用于去重和查询，不额外保存 Provider 原始载荷或用户身份信息。
        return cls(
            _construction_token=dto_construction_token(),
            comparison_product_id=comparison_product_id,
            external_review_id=review.external_review_id,
            reviewed_at=review.created_at,
            content=review.content,
            rating=review.rating,
            sku_text=review.sku_text,
            content_hash=hashlib.sha256(review.content.encode("utf-8")).hexdigest(),
            source=source_reference_payload(review.source),
            fetched_at=review.source.obtained_at,
        )

    @validates("source")
    def _validate_source(self, _key: str, value: object) -> dict[str, str]:
        """在 ORM 赋值边界拒绝缺失字段或携带额外键的来源 JSON。by AI.Coding"""
        return validate_source_reference_payload(value)

    @validates("rating")
    def _validate_rating(self, _key: str, value: int | None) -> int | None:
        """在 ORM 赋值边界复用评分纯校验。by AI.Coding"""
        return validate_rating(value)


class ReviewAnnotation(Base):
    """保存评论对已注册维度的单一有效注解。by AI.Coding"""

    __tablename__ = "review_annotations"
    __table_args__ = (
        UniqueConstraint(
            "review_id", "dimension_id", name="uq_review_annotations_review_dimension"
        ),
        CheckConstraint("sentiment IN ('positive', 'neutral', 'negative')", name="sentiment"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("raw_reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dimension_definitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sentiment: Mapped[ReviewSentiment] = mapped_column(
        Enum(
            ReviewSentiment,
            native_enum=False,
            create_constraint=False,
            length=8,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_runs.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    review: Mapped[RawReview] = relationship(back_populates="annotations")
    dimension: Mapped[DimensionDefinition] = relationship(back_populates="review_annotations")
    model_run: Mapped[ModelRun | None] = relationship(back_populates="annotations")

    @validates("confidence")
    def _validate_confidence(self, _key: str, value: float) -> float:
        """在 ORM 赋值边界复用置信度纯校验。by AI.Coding"""
        validated = validate_confidence(value)
        assert validated is not None
        return validated
