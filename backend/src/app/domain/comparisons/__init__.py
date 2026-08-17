"""对比任务领域状态与纯校验规则。by AI.Coding"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from app.core.errors import DomainConflictError, InputError
from app.providers.commerce.dto import NormalizedProductUrl


class ComparisonStatus(StrEnum):
    """定义对比任务持久化状态。by AI.Coding"""

    DRAFT = "draft"
    PARSING = "parsing"
    AWAITING_PRODUCT_CONFIRMATION = "awaiting_product_confirmation"
    AWAITING_DIMENSION_CONFIRMATION = "awaiting_dimension_confirmation"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    QUEUED = "queued"
    FETCHING = "fetching"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    DELETED = "deleted"


class TaskStage(StrEnum):
    """定义用户可见的任务处理阶段。by AI.Coding"""

    CREATED = "created"
    PRODUCT_PARSING = "product_parsing"
    PRODUCT_CONFIRMATION = "product_confirmation"
    DIMENSION_CONFIRMATION = "dimension_confirmation"
    QUEUED = "queued"
    DATA_FETCHING = "data_fetching"
    ANALYSIS = "analysis"
    REPORTING = "reporting"
    FINISHED = "finished"


class TaskEventType(StrEnum):
    """定义任务审计事件类型。by AI.Coding"""

    STATUS_CHANGED = "status_changed"
    PROGRESS_UPDATED = "progress_updated"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


_ALLOWED_TRANSITIONS: dict[ComparisonStatus, frozenset[ComparisonStatus]] = {
    ComparisonStatus.DRAFT: frozenset({ComparisonStatus.PARSING, ComparisonStatus.DELETED}),
    ComparisonStatus.PARSING: frozenset(
        {
            ComparisonStatus.AWAITING_PRODUCT_CONFIRMATION,
            ComparisonStatus.FAILED,
            ComparisonStatus.DELETED,
        }
    ),
    ComparisonStatus.AWAITING_PRODUCT_CONFIRMATION: frozenset(
        {
            ComparisonStatus.PARSING,
            ComparisonStatus.AWAITING_DIMENSION_CONFIRMATION,
            ComparisonStatus.DELETED,
        }
    ),
    ComparisonStatus.AWAITING_DIMENSION_CONFIRMATION: frozenset(
        {
            ComparisonStatus.AWAITING_PRODUCT_CONFIRMATION,
            ComparisonStatus.READY_FOR_ANALYSIS,
            ComparisonStatus.DELETED,
        }
    ),
    ComparisonStatus.READY_FOR_ANALYSIS: frozenset(
        {ComparisonStatus.QUEUED, ComparisonStatus.DELETED}
    ),
    ComparisonStatus.QUEUED: frozenset(
        {ComparisonStatus.FETCHING, ComparisonStatus.FAILED, ComparisonStatus.DELETED}
    ),
    ComparisonStatus.FETCHING: frozenset(
        {
            ComparisonStatus.PROCESSING,
            ComparisonStatus.PARTIALLY_COMPLETED,
            ComparisonStatus.FAILED,
            ComparisonStatus.DELETED,
        }
    ),
    ComparisonStatus.PROCESSING: frozenset(
        {
            ComparisonStatus.COMPLETED,
            ComparisonStatus.PARTIALLY_COMPLETED,
            ComparisonStatus.FAILED,
            ComparisonStatus.DELETED,
        }
    ),
    ComparisonStatus.COMPLETED: frozenset({ComparisonStatus.DELETED}),
    ComparisonStatus.PARTIALLY_COMPLETED: frozenset({ComparisonStatus.DELETED}),
    ComparisonStatus.FAILED: frozenset({ComparisonStatus.QUEUED, ComparisonStatus.DELETED}),
    ComparisonStatus.DELETED: frozenset(),
}


def validate_status_transition(
    current: ComparisonStatus, target: ComparisonStatus
) -> ComparisonStatus:
    """校验任务状态转换并返回目标状态。by AI.Coding"""
    # 相同状态不构成转换，允许幂等调用保持领域操作可重试。
    if current == target:
        return target
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise DomainConflictError(f"不允许从 {current.value} 转换为 {target.value}")
    return target


def validate_review_window(window_days: int) -> int:
    """校验评论时间窗口仅为 30 或 60 天。by AI.Coding"""
    if window_days not in {30, 60}:
        raise InputError("评论窗口只能是 30 或 60 天")
    return window_days


def validate_progress(progress: int) -> int:
    """校验任务进度范围。by AI.Coding"""
    if not 0 <= progress <= 100:
        raise InputError("进度必须在 0 到 100 之间")
    return progress


def validate_candidate_count[CandidateT](candidates: list[CandidateT]) -> list[CandidateT]:
    """校验一次对比只能包含 2 至 3 个候选商品。by AI.Coding"""
    if not 2 <= len(candidates) <= 3:
        raise InputError("候选商品数量必须为 2 到 3 个")
    return candidates


def validate_unique_candidates[CandidateT](
    candidates: list[CandidateT], *, key: Callable[[CandidateT], str]
) -> list[CandidateT]:
    """按规范化标识拒绝同一任务中的重复候选商品。by AI.Coding"""
    # 复用调用方已经完成安全规范化的稳定标识，不比较原始输入文本。
    normalized_keys = [key(candidate) for candidate in candidates]
    if len(normalized_keys) != len(set(normalized_keys)):
        raise DomainConflictError("候选商品经规范化后存在重复")
    return candidates


@dataclass(frozen=True)
class ComparableProduct:
    """承载基础可比性所需的候选标识与最新类别。by AI.Coding"""

    product_id: UUID
    category: str | None


@dataclass(frozen=True)
class ComparabilityWarning:
    """表示不会阻断确认的受控类别信息警告。by AI.Coding"""

    code: str
    message: str


def normalize_idempotency_key(value: str) -> str:
    """去除幂等键空白并校验受限长度。by AI.Coding"""
    # 仅返回规范化值供摘要计算，调用方绝不持久化该明文。
    normalized = value.strip()
    if not 8 <= len(normalized) <= 128:
        raise InputError("幂等键去除首尾空白后长度必须为 8 到 128")
    return normalized


def idempotency_key_hash(value: str) -> str:
    """计算规范化幂等键的不可逆 SHA-256 摘要。by AI.Coding"""
    # 将明文键限制在调用栈内，数据库和事件只使用固定长度摘要。
    return sha256(normalize_idempotency_key(value).encode()).hexdigest()


def create_request_fingerprint(
    products: Sequence[NormalizedProductUrl], review_window_days: int
) -> str:
    """按候选顺序和评论窗口计算确定性创建载荷摘要。by AI.Coding"""
    validate_review_window(review_window_days)
    # canonical URL 已移除不安全 query；保留数组顺序以区分不同候选顺序。
    payload = {
        "products": [
            {
                "canonical_url": str(product.canonical_url),
                "platform": product.platform,
                "external_product_id": product.external_product_id,
                "safe_url_fingerprint": product.safe_url_fingerprint,
            }
            for product in products
        ],
        "review_window_days": review_window_days,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode()).hexdigest()


def validate_confirmation_set(
    expected_product_ids: Collection[UUID], submitted_product_ids: Sequence[UUID]
) -> None:
    """验证确认项恰好覆盖任务内每个候选一次。by AI.Coding"""
    # 先拒绝提交重复项，避免 set 去重后掩盖调用方的重复确认意图。
    if len(submitted_product_ids) != len(set(submitted_product_ids)):
        raise InputError("确认项中存在重复商品")
    if set(expected_product_ids) != set(submitted_product_ids):
        raise InputError("确认项必须恰好覆盖任务内全部候选商品")


def normalize_category(value: str) -> str:
    """按 NFKC、大小写和空白规则归一化已知类别。by AI.Coding"""
    # 不做语义映射，只执行规格明确的确定性文本规范化。
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold().strip())


def validate_basic_comparability(
    products: Sequence[ComparableProduct],
) -> list[ComparabilityWarning]:
    """校验已知类别一致性并返回类别缺失警告。by AI.Coding"""
    known_categories = {
        normalize_category(product.category) for product in products if product.category
    }
    if len(known_categories) > 1:
        raise DomainConflictError("候选商品的已知类别不一致，无法进行基础对比")
    if any(product.category is None or not product.category.strip() for product in products):
        # 警告不包含商品标题、URL 或 Provider 原文，避免事件中泄露敏感内容。
        return [
            ComparabilityWarning(
                code="CATEGORY_INFORMATION_INCOMPLETE",
                message="部分候选商品缺少类别信息，已在基础可比性检查中放行。",
            )
        ]
    return []
