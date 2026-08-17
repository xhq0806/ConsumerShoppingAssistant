"""M1-D 动态维度确定性推荐规则。by AI.Coding"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.domain.dimensions import DimensionSourceType

DEFAULT_SELECTED_DIMENSION_COUNT = 8


class DimensionDataRisk(StrEnum):
    """表示当前候选商品对某维度的数据可用程度。by AI.Coding"""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DimensionCandidate:
    """承载推荐器所需的受控目录字段。by AI.Coding"""

    code: str
    name: str
    source_type: DimensionSourceType
    default_priority: int
    affects_recommendation: bool
    user_removable: bool
    aliases: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class DimensionRecommendation:
    """表示一个可持久化、可解释的任务维度推荐结果。by AI.Coding"""

    code: str
    name: str
    source_type: DimensionSourceType
    selected: bool
    position: int | None
    user_selected: bool
    reason: str
    data_risk: DimensionDataRisk
    has_difference: bool
    affects_recommendation: bool
    user_removable: bool
    description: str


def recommend_dimensions(
    candidates: Sequence[DimensionCandidate],
    *,
    product_values: Mapping[str, Sequence[str | None]],
    priority_concerns: Sequence[str],
) -> tuple[DimensionRecommendation, ...]:
    """按用户关注、商品差异、数据完整度和目录优先级生成稳定推荐。by AI.Coding"""
    normalized_concerns = tuple(_normalize_signal(item) for item in priority_concerns)
    scored: list[
        tuple[
            tuple[int, int, int, int, str],
            DimensionCandidate,
            bool,
            DimensionDataRisk,
            bool,
        ]
    ] = []
    for candidate in candidates:
        values = tuple(product_values.get(candidate.code, ()))
        risk = _data_risk(values)
        has_difference = _has_difference(values)
        concern_matched = _matches_concern(candidate, normalized_concerns)
        scored.append(
            (
                (
                    0 if concern_matched else 1,
                    0 if has_difference else 1,
                    _risk_order(risk),
                    candidate.default_priority,
                    candidate.code,
                ),
                candidate,
                concern_matched,
                risk,
                has_difference,
            )
        )
    scored.sort(key=lambda item: item[0])
    selected_count = min(DEFAULT_SELECTED_DIMENSION_COUNT, len(scored))
    recommendations: list[DimensionRecommendation] = []
    for index, (_, candidate, concern_matched, risk, has_difference) in enumerate(scored):
        selected = index < selected_count
        recommendations.append(
            DimensionRecommendation(
                code=candidate.code,
                name=candidate.name,
                source_type=candidate.source_type,
                selected=selected,
                position=index if selected else None,
                user_selected=False,
                reason=_selection_reason(
                    concern_matched=concern_matched,
                    has_difference=has_difference,
                    risk=risk,
                ),
                data_risk=risk,
                has_difference=has_difference,
                affects_recommendation=candidate.affects_recommendation,
                user_removable=candidate.user_removable,
                description=candidate.description,
            )
        )
    return tuple(recommendations)


def _matches_concern(candidate: DimensionCandidate, normalized_concerns: Sequence[str]) -> bool:
    """使用目录受控别名匹配用户关注文本，不创造新维度。by AI.Coding"""
    signals = {
        _normalize_signal(candidate.code),
        _normalize_signal(candidate.name),
        *(_normalize_signal(alias) for alias in candidate.aliases),
    }
    return any(
        signal and (signal in concern or concern in signal)
        for concern in normalized_concerns
        if concern
        for signal in signals
    )


def _normalize_signal(value: str) -> str:
    """对推荐匹配文本执行 NFKC、大小写折叠和空白收敛。by AI.Coding"""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold().strip())


def _data_risk(values: Sequence[str | None]) -> DimensionDataRisk:
    """根据候选商品维度值覆盖率给出受控风险。by AI.Coding"""
    available_count = sum(value is not None and value.strip() != "" for value in values)
    if available_count == 0:
        return DimensionDataRisk.UNAVAILABLE
    if available_count < len(values):
        return DimensionDataRisk.PARTIAL
    return DimensionDataRisk.AVAILABLE


def _has_difference(values: Sequence[str | None]) -> bool:
    """仅在至少两个已知值不同时标记商品差异。by AI.Coding"""
    known = {
        _normalize_signal(value) for value in values if value is not None and value.strip() != ""
    }
    return len(known) > 1


def _risk_order(risk: DimensionDataRisk) -> int:
    """把数据风险转换为稳定排序权重。by AI.Coding"""
    return {
        DimensionDataRisk.AVAILABLE: 0,
        DimensionDataRisk.PARTIAL: 1,
        DimensionDataRisk.UNAVAILABLE: 2,
    }[risk]


def _selection_reason(
    *,
    concern_matched: bool,
    has_difference: bool,
    risk: DimensionDataRisk,
) -> str:
    """生成不包含用户正文的受控推荐理由。by AI.Coding"""
    if concern_matched:
        return "匹配用户明确关注点"
    if has_difference:
        return "候选商品在该维度存在差异"
    if risk is DimensionDataRisk.PARTIAL:
        return "部分候选缺少该维度数据"
    if risk is DimensionDataRisk.UNAVAILABLE:
        return "当前阶段尚无完整数据来源"
    return "当前品类的常用对比项"
