"""M1-E 评论时间过滤、规范化和稳定去重规则。by AI.Coding"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.providers.commerce.dto import ReviewDTO

_MEANINGLESS_CONTENT = frozenset({"好评", "默认好评", "不错", "满意", "很好", "可以"})


@dataclass(frozen=True)
class ReviewCleaningResult:
    """表示一批评论清洗后的可持久化结果和受控计数。by AI.Coding"""

    fetched_count: int
    valid_reviews: tuple[ReviewDTO, ...]
    filtered_out_count: int
    duplicate_count: int


def normalize_review_content(content: str) -> str:
    """执行 Unicode NFKC、首尾去空白和连续空白收敛。by AI.Coding"""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", content).strip())


def clean_reviews(
    reviews: Sequence[ReviewDTO],
    *,
    window_days: int,
    actual_end_at: datetime | None,
) -> ReviewCleaningResult:
    """按确定性顺序过滤时间、无意义正文并进行商品内正文去重。by AI.Coding"""
    ordered = sorted(reviews, key=lambda item: (item.created_at, item.external_review_id))
    anchor = actual_end_at
    if anchor is None and ordered:
        anchor = max(review.created_at for review in ordered)
    cutoff = None if anchor is None else anchor - timedelta(days=window_days)
    seen_contents: set[str] = set()
    valid: list[ReviewDTO] = []
    filtered_out_count = 0
    duplicate_count = 0

    for review in ordered:
        # Provider 实际结束时间是时间窗口真源；超出窗口的记录不进入后续分析。
        if anchor is not None and (
            review.created_at > anchor or (cutoff is not None and review.created_at < cutoff)
        ):
            filtered_out_count += 1
            continue
        normalized = normalize_review_content(review.content)
        if not normalized or normalized.casefold() in _MEANINGLESS_CONTENT:
            filtered_out_count += 1
            continue
        deduplication_key = normalized
        if deduplication_key in seen_contents:
            duplicate_count += 1
            continue
        seen_contents.add(deduplication_key)
        valid.append(review.model_copy(update={"content": normalized}))

    return ReviewCleaningResult(
        fetched_count=len(reviews),
        valid_reviews=tuple(valid),
        filtered_out_count=filtered_out_count,
        duplicate_count=duplicate_count,
    )
