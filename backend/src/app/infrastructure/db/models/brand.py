"""T04 品牌主档与字段级来源 ORM。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.domain.brands import (
    BrandField,
    BrandSourceType,
    BrandVerificationStatus,
    normalize_brand_name,
    validate_confidence,
)
from app.infrastructure.db.base import Base, TimestampMixin


class BrandProfile(TimestampMixin, Base):
    """保存已核验或待核验的共享品牌主档。by AI.Coding"""

    __tablename__ = "brand_profiles"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'rejected')",
            name="verification_status",
        ),
        CheckConstraint(
            "founded_year IS NULL OR founded_year BETWEEN 1 AND 9999", name="founded_year"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    founded_year: Mapped[int | None] = mapped_column(Integer)
    parent_company: Mapped[str | None] = mapped_column(String(255))
    country_or_region: Mapped[str | None] = mapped_column(String(255))
    primary_categories: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    verification_status: Mapped[BrandVerificationStatus] = mapped_column(
        Enum(
            BrandVerificationStatus,
            native_enum=False,
            create_constraint=False,
            length=10,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=BrandVerificationStatus.UNVERIFIED,
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sources: Mapped[list[BrandSource]] = relationship(
        back_populates="brand", cascade="all, delete-orphan", passive_deletes=True
    )

    @classmethod
    def create(cls, *, display_name: str, aliases: list[str] | None = None) -> BrandProfile:
        """从展示名构建具有确定性标准名的品牌主档。by AI.Coding"""
        return cls(
            display_name=display_name.strip(),
            normalized_name=normalize_brand_name(display_name),
            aliases=list(aliases or []),
        )

    @validates("normalized_name")
    def _validate_normalized_name(self, _key: str, value: str) -> str:
        """阻止绕过确定性品牌名归一化。by AI.Coding"""
        return normalize_brand_name(value)


class BrandSource(Base):
    """保存品牌字段的独立来源记录并允许来源互相冲突。by AI.Coding"""

    __tablename__ = "brand_sources"
    __table_args__ = (
        CheckConstraint(
            "field_name IN ('founded_year', 'parent_company', 'country_or_region', "
            "'primary_categories')",
            name="field_name",
        ),
        CheckConstraint(
            "source_type IN ('official_website', 'trusted_knowledge_base', 'manual')",
            name="source_type",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[BrandField] = mapped_column(
        Enum(
            BrandField,
            native_enum=False,
            create_constraint=False,
            length=19,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    source_type: Mapped[BrandSourceType] = mapped_column(
        Enum(
            BrandSourceType,
            native_enum=False,
            create_constraint=False,
            length=22,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    brand: Mapped[BrandProfile] = relationship(back_populates="sources")

    @validates("confidence")
    def _validate_confidence(self, _key: str, value: float) -> float:
        """在 ORM 赋值边界复用可信度纯校验。by AI.Coding"""
        return validate_confidence(value)
