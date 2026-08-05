from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ImmutableModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class NormalizedProductUrl(ImmutableModel):
    canonical_url: HttpUrl
    platform: Literal["taobao"] = "taobao"
    host: str
    external_product_id: str
    safe_url_fingerprint: str


class SourceReference(ImmutableModel):
    provider: str
    source_id: str
    obtained_at: datetime


class SkuDTO(ImmutableModel):
    external_sku_id: str
    name: str
    attributes: dict[str, str] = Field(default_factory=dict)
    price: Decimal | None = None
    selectable: bool = True


class ProductDTO(ImmutableModel):
    external_product_id: str
    title: str
    image_url: HttpUrl | None = None
    brand: str | None = None
    category: str | None = None
    shop_name: str | None = None
    price: Decimal | None = None
    currency: str = "CNY"
    specifications: dict[str, str] = Field(default_factory=dict)
    after_sales: list[str] = Field(default_factory=list)
    source: SourceReference


class ProductRequest(ImmutableModel):
    product_url: NormalizedProductUrl


class ProductProviderResult(ImmutableModel):
    product: ProductDTO
    skus: list[SkuDTO] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReviewDTO(ImmutableModel):
    external_review_id: str
    created_at: datetime
    content: str
    rating: int | None = Field(default=None, ge=1, le=5)
    sku_text: str | None = None
    source: SourceReference


class ReviewFetchRequest(ImmutableModel):
    product_url: NormalizedProductUrl
    sku_id: str | None = None
    window_days: Literal[30, 60]
    max_reviews: int = Field(default=500, ge=1, le=5000)


class ReviewProviderResult(ImmutableModel):
    reviews: list[ReviewDTO] = Field(default_factory=list)
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    fetched_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_count(self) -> ReviewProviderResult:
        if self.fetched_count != len(self.reviews):
            raise ValueError("fetched_count 必须与 reviews 数量一致")
        return self


class ProviderFixtureEnvelope(ImmutableModel):
    kind: Literal["success", "error"]
    payload: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
