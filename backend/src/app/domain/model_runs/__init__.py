"""模型运行审计领域枚举与纯校验规则。by AI.Coding"""

from __future__ import annotations

from enum import StrEnum

from app.core.errors import InputError


class ModelRunStatus(StrEnum):
    """定义模型运行的受控结果状态。by AI.Coding"""

    SUCCESS = "success"
    ERROR = "error"


def validate_non_negative_count(value: int | None, *, field_name: str) -> int | None:
    """校验模型用量和时延均不为负。by AI.Coding"""
    if value is not None and value < 0:
        raise InputError(f"{field_name}不能为负数")
    return value


def validate_attempts(value: int) -> int:
    """校验 Gateway 首次调用即计为第一次尝试。by AI.Coding"""
    # attempts 表示实际发起的调用次数，因此零次不能形成模型运行审计记录。
    if value < 1:
        raise InputError("attempts 必须大于或等于 1")
    return value
