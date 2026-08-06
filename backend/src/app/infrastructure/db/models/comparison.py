"""T03 对比任务与候选商品 ORM。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.errors import DomainConflictError
from app.domain.comparisons import (
    ComparisonStatus,
    TaskEventType,
    TaskStage,
    validate_progress,
    validate_review_window,
    validate_status_transition,
)
from app.domain.products import (
    ProductParseStatus,
    ProductPlatform,
    validate_normalized_product_url,
)
from app.infrastructure.db.base import Base, TimestampMixin
from app.infrastructure.db.models._dto_construction import (
    dto_construction_token,
    require_dto_construction_token,
)
from app.providers.commerce.dto import NormalizedProductUrl

if TYPE_CHECKING:
    from app.infrastructure.db.models.dimension import TaskDimension
    from app.infrastructure.db.models.metric import AnalysisMetric
    from app.infrastructure.db.models.model_run import ModelRun
    from app.infrastructure.db.models.product import ProductSku, ProductSnapshot
    from app.infrastructure.db.models.report import ComparisonReport, FollowupMessage
    from app.infrastructure.db.models.review import RawReview


class ComparisonTask(TimestampMixin, Base):
    """表示可删除的对比任务聚合根。by AI.Coding"""

    __tablename__ = "comparison_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'parsing', 'awaiting_product_confirmation', "
            "'awaiting_dimension_confirmation', 'ready_for_analysis', 'queued', 'fetching', "
            "'processing', 'completed', 'partially_completed', 'failed', 'deleted')",
            name="status",
        ),
        CheckConstraint("review_window_days IN (30, 60)", name="review_window_days"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="progress"),
        Index("ix_comparison_tasks_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[ComparisonStatus] = mapped_column(
        Enum(
            ComparisonStatus,
            native_enum=False,
            create_constraint=False,
            length=31,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=ComparisonStatus.DRAFT,
        nullable=False,
    )
    review_window_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    partial_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))

    products: Mapped[list[ComparisonProduct]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", passive_deletes=True
    )
    events: Mapped[list[TaskEvent]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", passive_deletes=True
    )
    dimensions: Mapped[list[TaskDimension]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", passive_deletes=True
    )
    analysis_metrics: Mapped[list[AnalysisMetric]] = relationship(
        back_populates="comparison",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="analysis_metrics,comparison_product",
    )
    reports: Mapped[list[ComparisonReport]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", passive_deletes=True
    )
    followup_messages: Mapped[list[FollowupMessage]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", passive_deletes=True
    )
    model_runs: Mapped[list[ModelRun]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", passive_deletes=True
    )

    def __init__(
        self,
        *,
        status: ComparisonStatus | str = ComparisonStatus.DRAFT,
        review_window_days: int = 30,
        preferences: dict[str, Any] | None = None,
        progress: int = 0,
        partial_result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """仅以 draft 初始化新任务；SQLAlchemy 数据库装载会绕过此构造器。by AI.Coding"""
        # 显式赋值确保新实例立即拥有状态，并由同一 validator 拒绝非 draft 初态。
        self.status = ComparisonStatus(status)
        self.review_window_days = review_window_days
        self.preferences = {} if preferences is None else preferences
        self.progress = progress
        self.partial_result = partial_result
        self.error_code = error_code
        self.error_message = error_message

    @validates("status")
    def _validate_status(self, _key: str, value: ComparisonStatus | str) -> ComparisonStatus:
        """限制新任务为 draft，并让后续直接赋值统一经过状态机。by AI.Coding"""
        target = ComparisonStatus(value)
        current = self.__dict__.get("status")
        # SQLAlchemy 从数据库装载时不走 validates；普通 Python 构造首次赋值只能是 draft。
        if current is None:
            if target is not ComparisonStatus.DRAFT:
                raise DomainConflictError("新建对比任务的初始状态只能是 draft")
            return target
        return validate_status_transition(ComparisonStatus(current), target)

    @validates("review_window_days")
    def _validate_review_window(self, _key: str, value: int) -> int:
        """在 ORM 赋值边界复用评论窗口纯校验。by AI.Coding"""
        return validate_review_window(value)

    @validates("progress")
    def _validate_progress(self, _key: str, value: int) -> int:
        """在 ORM 赋值边界复用进度纯校验。by AI.Coding"""
        return validate_progress(value)


class ComparisonProduct(TimestampMixin, Base):
    """表示任务中的一个规范化候选商品。by AI.Coding"""

    __tablename__ = "comparison_products"
    __table_args__ = (
        UniqueConstraint("comparison_id", "id", name="uq_comparison_products_comparison_id_id"),
        UniqueConstraint(
            "comparison_id", "position", name="uq_comparison_products_comparison_id_position"
        ),
        UniqueConstraint(
            "comparison_id",
            "platform",
            "external_product_id",
            name="uq_comparison_products_task_platform_external_id",
        ),
        UniqueConstraint(
            "comparison_id",
            "safe_url_fingerprint",
            name="uq_comparison_products_task_fingerprint",
        ),
        Index("ix_comparison_products_safe_url_fingerprint", "safe_url_fingerprint"),
        ForeignKeyConstraint(
            ["selected_sku_id"],
            ["product_skus.id"],
            name="fk_comparison_products_selected_sku_id_product_skus",
            use_alter=True,
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["id", "selected_sku_id"],
            ["product_skus.comparison_product_id", "product_skus.id"],
            name="fk_comparison_products_selected_sku_belongs_to_product",
            use_alter=True,
        ),
        CheckConstraint(
            "platform IN ('taobao')",
            name="platform",
        ),
        CheckConstraint(
            "parse_status IN ('pending', 'parsing', 'parsed', 'needs_confirmation', 'failed')",
            name="parse_status",
        ),
        CheckConstraint("position >= 0", name="position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    platform: Mapped[ProductPlatform] = mapped_column(
        Enum(
            ProductPlatform,
            native_enum=False,
            create_constraint=False,
            length=6,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    external_product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    safe_url_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_sku_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parse_status: Mapped[ProductParseStatus] = mapped_column(
        Enum(
            ProductParseStatus,
            native_enum=False,
            create_constraint=False,
            length=18,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=ProductParseStatus.PENDING,
        nullable=False,
    )

    comparison: Mapped[ComparisonTask] = relationship(back_populates="products")
    snapshots: Mapped[list[ProductSnapshot]] = relationship(
        back_populates="comparison_product", cascade="all, delete-orphan", passive_deletes=True
    )
    skus: Mapped[list[ProductSku]] = relationship(
        back_populates="comparison_product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ProductSku.comparison_product_id",
    )
    selected_sku: Mapped[ProductSku | None] = relationship(
        foreign_keys=[selected_sku_id], post_update=True, viewonly=True
    )
    raw_reviews: Mapped[list[RawReview]] = relationship(
        back_populates="comparison_product", cascade="all, delete-orphan", passive_deletes=True
    )
    analysis_metrics: Mapped[list[AnalysisMetric]] = relationship(
        back_populates="comparison_product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="analysis_metrics,comparison",
    )

    def __init__(self, *, _construction_token: object | None = None, **values: Any) -> None:
        """拒绝绕过规范化 URL DTO 的普通 Python 直接构造。by AI.Coding"""
        require_dto_construction_token(_construction_token)
        # SQLAlchemy 数据库装载绕过 __init__；factory 只传入白名单列值。
        for key, value in values.items():
            setattr(self, key, value)

    @classmethod
    def _from_normalized_url(
        cls, *, comparison_id: uuid.UUID, position: int, product_url: NormalizedProductUrl
    ) -> ComparisonProduct:
        """仅从规范化 URL DTO 构造可持久化候选商品。by AI.Coding"""
        # 不提供 raw_url 参数，确保持久化边界只保存 canonical URL 与安全标识。
        normalized_url = validate_normalized_product_url(product_url)
        return cls(
            _construction_token=dto_construction_token(),
            comparison_id=comparison_id,
            position=position,
            canonical_url=str(normalized_url.canonical_url),
            platform=ProductPlatform(normalized_url.platform),
            external_product_id=normalized_url.external_product_id,
            safe_url_fingerprint=normalized_url.safe_url_fingerprint,
        )


class TaskEvent(Base):
    """表示任务阶段进度和脱敏审计事件。by AI.Coding"""

    __tablename__ = "task_events"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('created', 'product_parsing', 'product_confirmation', "
            "'dimension_confirmation', 'queued', 'data_fetching', 'analysis', 'reporting', "
            "'finished')",
            name="stage",
        ),
        CheckConstraint(
            "event_type IN ('status_changed', 'progress_updated', 'warning', 'error', 'info')",
            name="event_type",
        ),
        CheckConstraint("progress IS NULL OR progress BETWEEN 0 AND 100", name="progress"),
        Index("ix_task_events_comparison_id_created_at", "comparison_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_tasks.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[TaskStage] = mapped_column(
        Enum(
            TaskStage,
            native_enum=False,
            create_constraint=False,
            length=22,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    event_type: Mapped[TaskEventType] = mapped_column(
        Enum(
            TaskEventType,
            native_enum=False,
            create_constraint=False,
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    progress: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    comparison: Mapped[ComparisonTask] = relationship(back_populates="events")

    @validates("progress")
    def _validate_progress(self, _key: str, value: int | None) -> int | None:
        """校验可空事件进度。by AI.Coding"""
        return None if value is None else validate_progress(value)
