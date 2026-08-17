"""维度目录领域枚举与纯校验规则。by AI.Coding"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from enum import StrEnum

from app.core.errors import DomainConflictError, InputError


class DimensionDomain(StrEnum):
    """定义维度库的五类业务领域。by AI.Coding"""

    PRODUCT_FACT = "product_fact"
    BRAND_BACKGROUND = "brand_background"
    CATEGORY_SPECIFICATION = "category_specification"
    REVIEW_EXPERIENCE = "review_experience"
    USER_PREFERENCE = "user_preference"


class DimensionSourceType(StrEnum):
    """定义维度值所属的五种业务真源类型。by AI.Coding"""

    PRODUCT_FACT = "product_fact"
    BRAND_FACT = "brand_fact"
    REVIEW_METRIC = "review_metric"
    DERIVED_METRIC = "derived_metric"
    USER_PREFERENCE = "user_preference"


class DimensionValueType(StrEnum):
    """定义维度值的受控数据类型。by AI.Coding"""

    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    RATING = "rating"


class DimensionVisualization(StrEnum):
    """定义维度的受控展示方式。by AI.Coding"""

    TEXT = "text"
    TABLE = "table"
    BAR = "bar"
    RADAR = "radar"
    TREND = "trend"
    DISTRIBUTION = "distribution"


class MissingDataPolicy(StrEnum):
    """定义维度缺失数据的受控处理规则。by AI.Coding"""

    SHOW_UNKNOWN = "show_unknown"
    EXCLUDE_FROM_SCORING = "exclude_from_scoring"
    LOWER_CONFIDENCE = "lower_confidence"


def normalize_dimension_code(code: str) -> str:
    """生成稳定的 ASCII snake_case 维度 code。by AI.Coding"""
    # code 是跨模型标识，只允许确定性的英文小写、数字和下划线形式。
    normalized = unicodedata.normalize("NFKC", code).strip().lower()
    normalized = re.sub(r"[\s-]+", "_", normalized)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized):
        raise InputError("维度 code 必须是以字母开头的 ASCII snake_case")
    return normalized


def validate_registered_dimension[DimensionT](
    code: str, dimension: DimensionT | None, *, enabled: bool | None = None
) -> DimensionT:
    """拒绝未知或停用的维度 code，并返回已注册目录记录。by AI.Coding"""
    normalized = normalize_dimension_code(code)
    # 仓储负责查询，领域规则负责统一表达未知和停用目录冲突。
    if dimension is None:
        raise DomainConflictError(f"维度 {normalized} 未注册")
    if enabled is False:
        raise DomainConflictError(f"维度 {normalized} 已停用")
    return dimension


def validate_non_negative(value: int, *, field_name: str) -> int:
    """校验维度优先级和样本阈值为非负整数。by AI.Coding"""
    if value < 0:
        raise InputError(f"{field_name}不能为负数")
    return value


def validate_task_dimension_position(*, selected: bool, position: int | None) -> int | None:
    """校验仅选中维度具有非负排序位置。by AI.Coding"""
    if selected and position is None:
        raise InputError("选中维度必须提供排序位置")
    if not selected and position is not None:
        raise InputError("未选中维度不能占用排序位置")
    if position is not None and position < 0:
        raise InputError("维度排序位置不能为负数")
    return position


def validate_dimension_confirmation(codes: Sequence[str]) -> tuple[str, ...]:
    """规范化并校验维度确认列表非空且不重复。by AI.Coding"""
    if not codes:
        raise InputError("至少保留一个对比维度")
    normalized = tuple(normalize_dimension_code(code) for code in codes)
    if len(normalized) != len(set(normalized)):
        raise InputError("确认维度中存在重复项")
    return normalized
