"""M1-B 对比草稿、解析、详情与确认 API 契约。by AI.Coding"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _StrictSchema(BaseModel):
    """为 M1-B 输入输出 schema 统一禁止未声明字段。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")


class ComparisonCreateRequest(_StrictSchema):
    """定义创建对比草稿的请求体。by AI.Coding"""

    product_urls: list[str] = Field(min_length=2, max_length=3)
    review_window_days: Literal[30, 60]


class ProductConfirmationInput(_StrictSchema):
    """定义单个候选商品的 SKU 确认项。by AI.Coding"""

    comparison_product_id: UUID
    selected_sku_id: UUID | None


class ConfirmProductsRequest(_StrictSchema):
    """定义必须覆盖全部候选商品的确认请求体。by AI.Coding"""

    products: list[ProductConfirmationInput] = Field(min_length=2, max_length=3)


class ProductSkuResponse(_StrictSchema):
    """定义安全 SKU 响应白名单。by AI.Coding"""

    id: UUID
    external_sku_id: str
    name: str
    attributes: dict[str, str]
    price: Decimal | None
    selectable: bool


class ProductSnapshotResponse(_StrictSchema):
    """定义最新商品快照响应白名单。by AI.Coding"""

    id: UUID
    title: str
    image_url: str | None
    brand: str | None
    category: str | None
    shop_name: str | None
    price: Decimal | None
    currency: str
    specifications: dict[str, str]
    after_sales: list[str]
    source_provider: str
    source_id: str
    captured_at: datetime


class ComparisonProductResponse(_StrictSchema):
    """定义候选商品响应白名单且不返回原始 URL。by AI.Coding"""

    id: UUID
    position: int
    platform: str
    external_product_id: str
    parse_status: str
    selected_sku_id: UUID | None
    latest_snapshot: ProductSnapshotResponse | None
    skus: list[ProductSkuResponse]


class TaskEventResponse(_StrictSchema):
    """定义脱敏任务事件的响应格式。by AI.Coding"""

    id: UUID
    stage: str
    event_type: str
    progress: int | None
    message: str | None
    details: dict[str, object]
    created_at: datetime


class ComparabilityWarningResponse(_StrictSchema):
    """定义基础可比性警告的受控响应格式。by AI.Coding"""

    code: str
    message: str


class ComparisonSummaryResponse(_StrictSchema):
    """定义创建或幂等重放时返回的任务摘要。by AI.Coding"""

    id: UUID
    status: str
    review_window_days: int
    progress: int
    products: list[ComparisonProductResponse]


class ComparisonDetailResponse(ComparisonSummaryResponse):
    """定义包含最新快照、事件与警告的任务详情。by AI.Coding"""

    events: list[TaskEventResponse]
    warnings: list[ComparabilityWarningResponse]
