"""品牌目录领域枚举与纯校验规则。by AI.Coding"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from enum import StrEnum
from typing import Protocol

from app.core.errors import DomainConflictError, InputError


class BrandVerificationStatus(StrEnum):
    """定义品牌主档核验状态。by AI.Coding"""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class BrandField(StrEnum):
    """定义允许记录字段级来源的品牌事实。by AI.Coding"""

    FOUNDED_YEAR = "founded_year"
    PARENT_COMPANY = "parent_company"
    COUNTRY_OR_REGION = "country_or_region"
    PRIMARY_CATEGORIES = "primary_categories"


class BrandSourceType(StrEnum):
    """定义品牌事实的受控来源类别。by AI.Coding"""

    OFFICIAL_WEBSITE = "official_website"
    TRUSTED_KNOWLEDGE_BASE = "trusted_knowledge_base"
    MANUAL = "manual"


class BrandSourceValue(Protocol):
    """定义品牌来源冲突检测所需的最小结构。by AI.Coding"""

    @property
    def field_name(self) -> BrandField:
        """返回来源对应的品牌字段。by AI.Coding"""
        ...

    @property
    def value(self) -> object:
        """返回来源声明的字段值。by AI.Coding"""
        ...


def normalize_brand_name(name: str) -> str:
    """以 Unicode 兼容归一化生成确定性的品牌标准名。by AI.Coding"""
    # casefold 统一大小写，标点和空白统一为单个空格，避免展示差异破坏唯一性。
    normalized = unicodedata.normalize("NFKC", name).casefold().strip()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    normalized = " ".join(normalized.split())
    if not normalized:
        raise InputError("品牌名称归一化后不能为空")
    return normalized


def validate_confidence(confidence: float) -> float:
    """校验品牌字段来源可信度范围。by AI.Coding"""
    if not 0 <= confidence <= 1:
        raise InputError("可信度必须在 0 到 1 之间")
    return confidence


def find_conflicting_brand_fields(sources: Iterable[BrandSourceValue]) -> set[BrandField]:
    """返回存在多个不同来源值的品牌字段集合。by AI.Coding"""
    # 用稳定 JSON 表达比较异构标量、列表和对象，同时保留数据库中的全部来源记录。
    values_by_field: dict[BrandField, set[str]] = {}
    for source in sources:
        stable_value = json.dumps(source.value, ensure_ascii=False, sort_keys=True, default=str)
        values_by_field.setdefault(source.field_name, set()).add(stable_value)
    return {field for field, values in values_by_field.items() if len(values) > 1}


def validate_brand_field_for_scoring(
    field_name: BrandField, *, has_value: bool, has_conflict: bool
) -> BrandField:
    """拒绝未知、冲突或仅可展示的品牌事实参与自动计分。by AI.Coding"""
    # 成立年份只承载背景展示，品牌历史长短不能替代产品证据。
    if field_name is BrandField.FOUNDED_YEAR:
        raise DomainConflictError("品牌成立年份只能展示，不能参与自动计分")
    if not has_value:
        raise DomainConflictError("未知品牌字段不能参与自动计分")
    if has_conflict:
        raise DomainConflictError("存在冲突来源的品牌字段不能参与自动计分")
    return field_name
