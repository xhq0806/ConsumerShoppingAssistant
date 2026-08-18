"""M1-B 对比草稿、解析、详情与确认 API 契约。by AI.Coding"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
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


PreferenceText = Annotated[str, Field(min_length=1)]


class UpdatePreferencesRequest(_StrictSchema):
    """定义评论窗口和用户购买偏好的整体替换请求。by AI.Coding"""

    review_window_days: Literal[30, 60]
    budget_min: Decimal | None = Field(default=None, ge=0, le=1_000_000, decimal_places=2)
    budget_max: Decimal | None = Field(default=None, ge=0, le=1_000_000, decimal_places=2)
    usage_scenarios: list[PreferenceText] = Field(min_length=1)
    priority_concerns: list[PreferenceText] = Field(min_length=1)
    deal_breakers: list[PreferenceText] = Field(default_factory=list)


DimensionCode = Annotated[str, Field(min_length=1, max_length=100)]


class ConfirmDimensionsRequest(_StrictSchema):
    """定义最终确认的唯一有序维度 code 列表。by AI.Coding"""

    dimension_codes: list[DimensionCode] = Field(min_length=1, max_length=20)


class UserPreferencesResponse(_StrictSchema):
    """定义可恢复的规范化用户偏好响应。by AI.Coding"""

    budget_min: Decimal | None
    budget_max: Decimal | None
    usage_scenarios: list[str]
    priority_concerns: list[str]
    deal_breakers: list[str]


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


class DimensionRecommendationResponse(_StrictSchema):
    """定义单个动态维度的安全展示和恢复字段。by AI.Coding"""

    code: str
    name: str
    source_type: str
    selected: bool
    position: int | None
    user_selected: bool
    reason: str
    data_risk: Literal["available", "partial", "unavailable"]
    has_difference: bool
    affects_recommendation: bool
    user_removable: bool
    description: str


class DimensionSetResponse(_StrictSchema):
    """定义任务动态维度集合响应。by AI.Coding"""

    comparison_id: UUID
    status: str
    category: str | None
    generated: bool
    dimensions: list[DimensionRecommendationResponse]


class AnalysisProgressResponse(_StrictSchema):
    """定义评论采集、智能注解和指标计算的安全恢复结构。by AI.Coding"""

    comparison_id: UUID
    status: str
    progress: int
    stage: str
    message: str
    fetched_review_count: int
    valid_review_count: int
    annotated_review_count: int
    annotation_count: int
    metric_count: int
    can_retry: bool
    polling_complete: bool


class ComparisonSummaryResponse(_StrictSchema):
    """定义创建或幂等重放时返回的任务摘要。by AI.Coding"""

    id: UUID
    status: str
    review_window_days: int
    progress: int
    products: list[ComparisonProductResponse]
    preferences: UserPreferencesResponse | None


class ComparisonDetailResponse(ComparisonSummaryResponse):
    """定义包含最新快照、事件与警告的任务详情。by AI.Coding"""

    events: list[TaskEventResponse]
    warnings: list[ComparabilityWarningResponse]
