"""T03 商品快照与 SKU ORM。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.domain.products import source_reference_payload, validate_price
from app.infrastructure.db.base import Base
from app.infrastructure.db.models._dto_construction import (
    dto_construction_token,
    require_dto_construction_token,
)
from app.providers.commerce.dto import ProductDTO, SkuDTO


class ProductSnapshot(Base):
    """保存候选商品不可覆盖的事实快照。by AI.Coding"""

    __tablename__ = "product_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    brand: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255))
    shop_name: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    specifications: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, nullable=False)
    after_sales: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    source: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    comparison_product: Mapped[ComparisonProduct] = relationship(back_populates="snapshots")

    def __init__(self, *, _construction_token: object | None = None, **values: object) -> None:
        """拒绝绕过 ProductDTO 白名单的普通 Python 直接构造。by AI.Coding"""
        require_dto_construction_token(_construction_token)
        for key, value in values.items():
            setattr(self, key, value)

    @classmethod
    def _from_dto(cls, *, comparison_product_id: uuid.UUID, product: ProductDTO) -> ProductSnapshot:
        """从不可变商品 DTO 建立最小事实快照。by AI.Coding"""
        # 只映射 DTO 白名单字段，保留结构化来源而不保存完整响应。
        return cls(
            _construction_token=dto_construction_token(),
            comparison_product_id=comparison_product_id,
            title=product.title,
            image_url=None if product.image_url is None else str(product.image_url),
            brand=product.brand,
            category=product.category,
            shop_name=product.shop_name,
            price=validate_price(product.price),
            currency=product.currency,
            specifications=dict(product.specifications),
            after_sales=list(product.after_sales),
            source=source_reference_payload(product.source),
            captured_at=product.source.obtained_at,
        )

    @validates("price")
    def _validate_price(self, _key: str, value: Decimal | None) -> Decimal | None:
        """校验快照价格非负。by AI.Coding"""
        return validate_price(value)


class ProductSku(Base):
    """保存候选商品下可选择的 SKU。by AI.Coding"""

    __tablename__ = "product_skus"
    __table_args__ = (
        UniqueConstraint("comparison_product_id", "external_sku_id"),
        UniqueConstraint("comparison_product_id", "id", name="uq_product_skus_product_id_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_sku_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    attributes: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    selectable: Mapped[bool] = mapped_column(default=True, nullable=False)

    comparison_product: Mapped[ComparisonProduct] = relationship(
        back_populates="skus", foreign_keys=[comparison_product_id]
    )
    selected_by_product: Mapped[ComparisonProduct | None] = relationship(
        back_populates="selected_sku",
        foreign_keys="ComparisonProduct.selected_sku_id",
        viewonly=True,
    )

    def __init__(self, *, _construction_token: object | None = None, **values: object) -> None:
        """拒绝绕过 SkuDTO 白名单的普通 Python 直接构造。by AI.Coding"""
        require_dto_construction_token(_construction_token)
        for key, value in values.items():
            setattr(self, key, value)

    @classmethod
    def _from_dto(cls, *, comparison_product_id: uuid.UUID, sku: SkuDTO) -> ProductSku:
        """从不可变 SKU DTO 构建候选 SKU。by AI.Coding"""
        return cls(
            _construction_token=dto_construction_token(),
            comparison_product_id=comparison_product_id,
            external_sku_id=sku.external_sku_id,
            name=sku.name,
            attributes=dict(sku.attributes),
            price=validate_price(sku.price),
            selectable=sku.selectable,
        )

    @validates("price")
    def _validate_price(self, _key: str, value: Decimal | None) -> Decimal | None:
        """校验 SKU 价格非负。by AI.Coding"""
        return validate_price(value)


from app.infrastructure.db.models.comparison import ComparisonProduct  # noqa: E402
