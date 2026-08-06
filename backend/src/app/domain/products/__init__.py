"""商品领域枚举及规范化 DTO 校验。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from app.core.errors import DomainConflictError, InputError
from app.providers.commerce.dto import NormalizedProductUrl, SourceReference


class SkuSelectionCandidate(Protocol):
    """定义 SKU 选择校验所需的最小只读结构。by AI.Coding"""

    @property
    def id(self) -> uuid.UUID:
        """返回 SKU 标识。by AI.Coding"""
        ...

    @property
    def comparison_product_id(self) -> uuid.UUID:
        """返回 SKU 所属候选商品标识。by AI.Coding"""
        ...

    @property
    def selectable(self) -> bool:
        """返回 SKU 当前是否可选。by AI.Coding"""
        ...


class ProductPlatform(StrEnum):
    """定义当前允许持久化的商品平台。by AI.Coding"""

    TAOBAO = "taobao"


class ProductParseStatus(StrEnum):
    """定义候选商品解析状态。by AI.Coding"""

    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    NEEDS_CONFIRMATION = "needs_confirmation"
    FAILED = "failed"


def validate_normalized_product_url(value: NormalizedProductUrl) -> NormalizedProductUrl:
    """验证持久化输入是既有规范化 URL DTO。by AI.Coding"""
    # 只接受 DTO 暴露的 canonical URL、平台、外部 ID 与指纹，不接收原始 URL。
    if value.platform != ProductPlatform.TAOBAO.value:
        raise InputError("当前仅支持 taobao 平台")
    if not value.external_product_id or not value.safe_url_fingerprint:
        raise InputError("规范化商品 URL 缺少外部商品 ID 或安全指纹")
    return value


def validate_price(price: Decimal | None) -> Decimal | None:
    """校验价格为非负精确小数。by AI.Coding"""
    if price is not None and price < Decimal("0"):
        raise InputError("价格不能为负数")
    return price


def validate_sku_selection(
    *,
    comparison_product_id: uuid.UUID,
    selected_sku_id: uuid.UUID,
    skus: Iterable[SkuSelectionCandidate],
) -> uuid.UUID:
    """校验所选 SKU 存在、归属当前商品且处于可选状态。by AI.Coding"""
    # 先按 ID 查找，避免把未知 SKU 与跨商品 SKU 静默视为未选择。
    selected = next((sku for sku in skus if sku.id == selected_sku_id), None)
    if selected is None:
        raise DomainConflictError("所选 SKU 不存在于当前候选集合")
    if selected.comparison_product_id != comparison_product_id:
        raise DomainConflictError("所选 SKU 不属于当前商品")
    if not selected.selectable:
        raise DomainConflictError("所选 SKU 当前不可选择")
    return selected_sku_id


def validate_source_reference_payload(value: object) -> dict[str, str]:
    """严格校验持久化来源仅含 provider/source_id/obtained_at 三个字符串键。by AI.Coding"""
    if not isinstance(value, dict):
        raise InputError("来源引用必须是对象")
    required_keys = {"provider", "source_id", "obtained_at"}
    if set(value) != required_keys or any(not isinstance(value[key], str) for key in required_keys):
        raise InputError("来源引用必须且只能包含 provider、source_id、obtained_at 字符串字段")
    if any(not value[key] for key in required_keys):
        raise InputError("来源引用字段不能为空")
    return {key: value[key] for key in ("provider", "source_id", "obtained_at")}


def source_reference_payload(source: SourceReference) -> dict[str, str]:
    """将来源 DTO 映射为最小白名单 JSON。by AI.Coding"""
    # 明确列出允许持久化字段，避免保存完整 Provider payload。
    return {
        "provider": source.provider,
        "source_id": source.source_id,
        "obtained_at": source.obtained_at.isoformat(),
    }
