"""对比任务领域状态与纯校验规则。by AI.Coding"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from app.core.errors import DomainConflictError, InputError


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
    ComparisonStatus.FAILED: frozenset({ComparisonStatus.DELETED}),
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
