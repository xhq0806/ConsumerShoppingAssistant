"""M1-C 用户购买偏好值对象与持久化白名单。by AI.Coding"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.errors import InputError
from app.core.json_security import validate_no_sensitive_json_keys

_MAX_BUDGET = Decimal("1000000.00")
_MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class UserPreferences:
    """保存经过规范化的预算、场景、关注点和禁忌项。by AI.Coding"""

    budget_min: Decimal | None
    budget_max: Decimal | None
    usage_scenarios: tuple[str, ...]
    priority_concerns: tuple[str, ...]
    deal_breakers: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        budget_min: Decimal | str | None,
        budget_max: Decimal | str | None,
        usage_scenarios: Sequence[str],
        priority_concerns: Sequence[str],
        deal_breakers: Sequence[str],
    ) -> UserPreferences:
        """校验并构造规范化偏好。by AI.Coding"""
        normalized_min = _normalize_budget(budget_min, field_name="预算下限")
        normalized_max = _normalize_budget(budget_max, field_name="预算上限")
        if (
            normalized_min is not None
            and normalized_max is not None
            and normalized_max < normalized_min
        ):
            raise InputError("预算上限不能低于预算下限")
        # 所有文本集合在同一领域入口完成 NFKC、空白和稳定去重处理。
        return cls(
            budget_min=normalized_min,
            budget_max=normalized_max,
            usage_scenarios=_normalize_items(
                usage_scenarios, field_name="使用场景", minimum=1, maximum=5
            ),
            priority_concerns=_normalize_items(
                priority_concerns, field_name="关注点", minimum=1, maximum=8
            ),
            deal_breakers=_normalize_items(
                deal_breakers, field_name="禁忌项", minimum=0, maximum=8
            ),
        )

    @classmethod
    def from_persisted(cls, value: Mapping[str, Any] | None) -> UserPreferences | None:
        """从既有 JSONB 白名单字段恢复偏好；空对象表示尚未填写。by AI.Coding"""
        if not value:
            return None
        return cls.create(
            budget_min=_optional_string(value.get("budget_min")),
            budget_max=_optional_string(value.get("budget_max")),
            usage_scenarios=_string_sequence(value.get("usage_scenarios")),
            priority_concerns=_string_sequence(value.get("priority_concerns")),
            deal_breakers=_string_sequence(value.get("deal_breakers")),
        )

    def to_persisted(self) -> dict[str, object]:
        """转换为可安全写入 PostgreSQL JSONB 的固定字段结构。by AI.Coding"""
        payload: dict[str, object] = {
            "budget_min": _format_budget(self.budget_min),
            "budget_max": _format_budget(self.budget_max),
            "usage_scenarios": list(self.usage_scenarios),
            "priority_concerns": list(self.priority_concerns),
            "deal_breakers": list(self.deal_breakers),
        }
        # 复用公共敏感键门禁，防止未来扩展时把凭据类字段带入任务 JSONB。
        validate_no_sensitive_json_keys(payload)
        return payload


def _normalize_budget(value: Decimal | str | None, *, field_name: str) -> Decimal | None:
    """校验可空金额范围和两位小数精度。by AI.Coding"""
    if value is None or value == "":
        return None
    try:
        amount = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise InputError(f"{field_name}必须是有效金额") from error
    if not amount.is_finite() or amount < 0 or amount > _MAX_BUDGET:
        raise InputError(f"{field_name}必须在 0 到 1000000 之间")
    if amount.quantize(_MONEY_QUANTUM) != amount:
        raise InputError(f"{field_name}最多保留两位小数")
    return amount.quantize(_MONEY_QUANTUM)


def _normalize_items(
    values: Sequence[str], *, field_name: str, minimum: int, maximum: int
) -> tuple[str, ...]:
    """规范化文本集合并按不区分大小写的键稳定去重。by AI.Coding"""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        text = re.sub(
            r"\s+",
            " ",
            unicodedata.normalize("NFKC", str(raw_value)).strip(),
        )
        if not text:
            raise InputError(f"{field_name}不能包含空项")
        if len(text) > 80:
            raise InputError(f"{field_name}单项不能超过 80 个字符")
        key = text.casefold()
        if key not in seen:
            normalized.append(text)
            seen.add(key)
    if not minimum <= len(normalized) <= maximum:
        raise InputError(f"{field_name}数量必须在 {minimum} 到 {maximum} 之间")
    return tuple(normalized)


def _format_budget(value: Decimal | None) -> str | None:
    """将可空金额固定序列化为两位小数字符串。by AI.Coding"""
    return None if value is None else format(value, ".2f")


def _optional_string(value: object) -> str | None:
    """读取 JSONB 中的可空金额字符串。by AI.Coding"""
    return None if value is None else str(value)


def _string_sequence(value: object) -> tuple[str, ...]:
    """把 JSONB 数组转换为文本序列并拒绝错误结构。by AI.Coding"""
    if not isinstance(value, list | tuple):
        raise InputError("偏好 JSON 结构无效")
    return tuple(str(item) for item in value)
