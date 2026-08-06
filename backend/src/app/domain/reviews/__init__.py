"""评论注解领域枚举与纯校验规则。by AI.Coding"""

from __future__ import annotations

from enum import StrEnum

from app.core.errors import InputError


class ReviewSentiment(StrEnum):
    """定义评论维度注解的受控情感。by AI.Coding"""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


def validate_rating(rating: int | None) -> int | None:
    """校验可空评论评分为一至五星。by AI.Coding"""
    if rating is not None and not 1 <= rating <= 5:
        raise InputError("评论评分必须在 1 到 5 之间")
    return rating


def validate_confidence(confidence: float | None) -> float | None:
    """校验可空置信度位于闭区间零至一。by AI.Coding"""
    if confidence is not None and not 0 <= confidence <= 1:
        raise InputError("置信度必须在 0 到 1 之间")
    return confidence


def validate_review_evidence(*, content: str, evidence: str) -> str:
    """校验证据为评论正文中的非空连续子串。by AI.Coding"""
    # 只接受原文连续片段，避免模型生成无法追溯的改写证据。
    if not evidence or evidence not in content:
        raise InputError("注解证据必须是评论正文的非空连续子串")
    return evidence
