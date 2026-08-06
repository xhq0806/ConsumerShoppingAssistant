"""T05 评论、报告与模型审计领域规则测试。by AI.Coding"""

import uuid
from dataclasses import dataclass

import pytest

from app.core.errors import DomainConflictError, InputError
from app.domain.metrics import validate_metric_source_refs
from app.domain.model_runs import validate_attempts, validate_non_negative_count
from app.domain.reports import (
    ClaimSourceRef,
    ClaimSourceType,
    ReportStatus,
    validate_claim_source_refs,
    validate_report_publish,
    validate_report_version,
)
from app.domain.reviews import (
    ReviewSentiment,
    validate_confidence,
    validate_rating,
    validate_review_evidence,
)


@dataclass(frozen=True)
class Claim:
    """提供报告发布纯校验所需的最小 claim。by AI.Coding"""

    source_refs: list[dict[str, str]]


def test_review_evidence_must_be_contiguous_substring() -> None:
    """证据必须逐字出现在评论正文中。by AI.Coding"""
    assert validate_review_evidence(content="续航很好而且安静", evidence="很好而且") == "很好而且"
    with pytest.raises(InputError, match="连续子串"):
        validate_review_evidence(content="续航很好而且安静", evidence="续航安静")


@pytest.mark.parametrize("rating", [1, 3, 5, None])
def test_rating_accepts_valid_values(rating: int | None) -> None:
    """评分接受一至五和未知值。by AI.Coding"""
    assert validate_rating(rating) == rating


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_confidence_rejects_invalid_values(value: float) -> None:
    """置信度拒绝闭区间以外数值。by AI.Coding"""
    with pytest.raises(InputError, match="置信度"):
        validate_confidence(value)


def test_claim_requires_strict_controlled_source() -> None:
    """报告结论只接受受控类型、UUID 和类型专属必要字段。by AI.Coding"""
    metric_id = uuid.uuid4()
    assert validate_claim_source_refs([{"type": "analysis_metric", "id": str(metric_id)}]) == [
        {"type": "analysis_metric", "id": str(metric_id)}
    ]
    with pytest.raises(InputError, match="至少"):
        validate_claim_source_refs([])
    with pytest.raises(InputError):
        validate_claim_source_refs([{}])
    with pytest.raises(InputError, match="敏感键"):
        validate_claim_source_refs(
            [{"type": "analysis_metric", "id": str(metric_id), "authorization": "secret"}]
        )


def test_report_publish_checks_each_claim_source_exists() -> None:
    """completed/partial 前每个 claim 的来源必须存在于解析结果集合。by AI.Coding"""
    metric_id = uuid.uuid4()
    payload = {"type": "analysis_metric", "id": str(metric_id)}
    existing = ClaimSourceRef(ClaimSourceType.ANALYSIS_METRIC, metric_id)
    assert (
        validate_report_publish(
            status=ReportStatus.COMPLETED,
            claims=[Claim([payload])],
            existing_refs={existing},
        )
        is ReportStatus.COMPLETED
    )
    with pytest.raises(DomainConflictError, match="不存在"):
        validate_report_publish(
            status=ReportStatus.PARTIAL,
            claims=[Claim([payload])],
            existing_refs=set(),
        )


def test_metric_requires_at_least_one_input_source() -> None:
    """可复算指标即使是任务级计算也必须引用输入记录。by AI.Coding"""
    assert validate_metric_source_refs([{"kind": "review", "id": "r1"}]) == [
        {"kind": "review", "id": "r1"}
    ]
    with pytest.raises(InputError, match="输入来源"):
        validate_metric_source_refs([])


def test_published_report_statuses_are_explicit() -> None:
    """发布结果必须明确区分完整完成和部分完成。by AI.Coding"""
    assert ReportStatus.COMPLETED.value == "completed"
    assert ReportStatus.PARTIAL.value == "partial"
    assert "ready" not in {status.value for status in ReportStatus}


def test_review_sentiment_is_limited_to_three_product_values() -> None:
    """评论情感只允许产品规则定义的正向、中性和负向。by AI.Coding"""
    assert {sentiment.value for sentiment in ReviewSentiment} == {
        "positive",
        "neutral",
        "negative",
    }


def test_report_version_and_model_counts_are_non_negative() -> None:
    """报告版本从一开始且模型计数不允许负数。by AI.Coding"""
    with pytest.raises(InputError, match="版本"):
        validate_report_version(0)
    with pytest.raises(InputError, match="不能为负"):
        validate_non_negative_count(-1, field_name="latency_ms")
    assert validate_attempts(1) == 1
    with pytest.raises(InputError, match="大于或等于 1"):
        validate_attempts(0)
