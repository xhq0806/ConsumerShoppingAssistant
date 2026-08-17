"""T03 领域规则单元测试。by AI.Coding"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.core.errors import DomainConflictError, InputError
from app.domain.comparisons import (
    ComparisonStatus,
    validate_candidate_count,
    validate_progress,
    validate_review_window,
    validate_status_transition,
    validate_unique_candidates,
)
from app.domain.products import validate_price, validate_sku_selection
from app.infrastructure.db.models import ComparisonTask


@dataclass(frozen=True)
class Candidate:
    """提供候选重复校验所需的最小测试结构。by AI.Coding"""

    fingerprint: str


@dataclass(frozen=True)
class SkuCandidate:
    """提供 SKU 选择校验所需的最小测试结构。by AI.Coding"""

    id: uuid.UUID
    comparison_product_id: uuid.UUID
    selectable: bool


def test_status_transition_accepts_declared_path() -> None:
    """合法状态转换应返回目标状态。by AI.Coding"""
    assert (
        validate_status_transition(ComparisonStatus.DRAFT, ComparisonStatus.PARSING)
        is ComparisonStatus.PARSING
    )


def test_task_direct_status_assignment_uses_transition_validator() -> None:
    """实体直接赋值不能绕过 draft 到 completed 的状态机限制。by AI.Coding"""
    task = ComparisonTask()
    assert task.status is ComparisonStatus.DRAFT
    task.status = ComparisonStatus.PARSING
    assert task.status is ComparisonStatus.PARSING
    with pytest.raises(DomainConflictError, match="不允许"):
        task.status = ComparisonStatus.COMPLETED
    with pytest.raises(DomainConflictError, match="初始状态"):
        ComparisonTask(status=ComparisonStatus.COMPLETED)


def test_terminal_status_cannot_return_to_working_state() -> None:
    """终态不得回写到工作态。by AI.Coding"""
    with pytest.raises(DomainConflictError, match="不允许"):
        validate_status_transition(ComparisonStatus.COMPLETED, ComparisonStatus.PROCESSING)


def test_failed_task_can_be_requeued_by_guarded_application_use_case() -> None:
    """领域状态图允许应用层对可重试分析失败重新排队。by AI.Coding"""
    assert (
        validate_status_transition(ComparisonStatus.FAILED, ComparisonStatus.QUEUED)
        is ComparisonStatus.QUEUED
    )


@pytest.mark.parametrize("value", [30, 60])
def test_review_window_accepts_supported_values(value: int) -> None:
    """评论窗口接受 30 和 60 天。by AI.Coding"""
    assert validate_review_window(value) == value


@pytest.mark.parametrize("value", [-1, 101])
def test_progress_rejects_out_of_range_values(value: int) -> None:
    """进度拒绝边界外数值。by AI.Coding"""
    with pytest.raises(InputError, match="进度"):
        validate_progress(value)


def test_price_rejects_negative_decimal() -> None:
    """价格校验拒绝负精确小数。by AI.Coding"""
    with pytest.raises(InputError, match="价格"):
        validate_price(Decimal("-0.01"))


@pytest.mark.parametrize("count", [2, 3])
def test_candidate_count_accepts_two_or_three(count: int) -> None:
    """候选商品数量接受已批准的 2 至 3 个范围。by AI.Coding"""
    candidates = [Candidate(str(index)) for index in range(count)]
    assert validate_candidate_count(candidates) is candidates


@pytest.mark.parametrize("count", [0, 1, 4])
def test_candidate_count_rejects_outside_range(count: int) -> None:
    """候选商品数量拒绝少于 2 个或多于 3 个。by AI.Coding"""
    with pytest.raises(InputError, match="2 到 3"):
        validate_candidate_count([Candidate(str(index)) for index in range(count)])


def test_normalized_candidate_duplicates_are_rejected() -> None:
    """规范化后指纹相同的候选商品应视为重复。by AI.Coding"""
    candidates = [Candidate("same"), Candidate("same")]
    with pytest.raises(DomainConflictError, match="重复"):
        validate_unique_candidates(candidates, key=lambda candidate: candidate.fingerprint)


def test_sku_selection_requires_ownership_and_selectability() -> None:
    """SKU 选择只接受当前商品下可选的候选。by AI.Coding"""
    product_id = uuid.uuid4()
    sku = SkuCandidate(uuid.uuid4(), product_id, True)
    assert (
        validate_sku_selection(comparison_product_id=product_id, selected_sku_id=sku.id, skus=[sku])
        == sku.id
    )


@pytest.mark.parametrize("kind", ["missing", "foreign", "unselectable"])
def test_sku_selection_rejects_invalid_candidate(kind: str) -> None:
    """SKU 选择拒绝未知、跨商品或不可选候选。by AI.Coding"""
    product_id = uuid.uuid4()
    selected_sku_id = uuid.uuid4()
    if kind == "missing":
        skus: list[SkuCandidate] = []
    elif kind == "foreign":
        skus = [SkuCandidate(selected_sku_id, uuid.uuid4(), True)]
    else:
        skus = [SkuCandidate(selected_sku_id, product_id, False)]

    with pytest.raises(DomainConflictError):
        validate_sku_selection(
            comparison_product_id=product_id,
            selected_sku_id=selected_sku_id,
            skus=skus,
        )
