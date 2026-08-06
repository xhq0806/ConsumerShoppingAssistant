"""确定性分析指标的来源引用规则。by AI.Coding"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.errors import InputError


def validate_metric_source_refs(
    source_refs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """校验可复算指标至少引用一条非空输入记录。by AI.Coding"""
    # 任务级计算同样必须引用其输入记录，不能以“无外部源”为由省略复算链路。
    refs = [dict(source_ref) for source_ref in source_refs]
    if not refs or any(not source_ref for source_ref in refs):
        raise InputError("可复算指标必须至少关联一个非空输入来源引用")
    return refs
