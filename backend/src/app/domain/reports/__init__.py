"""报告领域枚举与纯校验规则。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from app.core.errors import DomainConflictError, InputError
from app.core.json_security import validate_no_sensitive_json_keys


class ReportStatus(StrEnum):
    """定义版本化报告的受控状态。by AI.Coding"""

    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ReportClaimType(StrEnum):
    """定义报告结论的受控业务类型。by AI.Coding"""

    FACT = "fact"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"


class ClaimSourceType(StrEnum):
    """定义 claim 可引用的四类已持久化事实来源。by AI.Coding"""

    PRODUCT_SNAPSHOT = "product_snapshot"
    BRAND_SOURCE = "brand_source"
    ANALYSIS_METRIC = "analysis_metric"
    RAW_REVIEW = "raw_review"


class FollowupRole(StrEnum):
    """定义受限追问历史中的消息角色。by AI.Coding"""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ClaimSourceRef:
    """表示通过严格结构校验的 claim 来源引用。by AI.Coding"""

    source_type: ClaimSourceType
    id: uuid.UUID
    field: str | None = None
    evidence: str | None = None

    def key(self) -> tuple[ClaimSourceType, uuid.UUID, str | None, str | None]:
        """返回可用于存在性集合比较的稳定键。by AI.Coding"""
        return (self.source_type, self.id, self.field, self.evidence)

    def to_payload(self) -> dict[str, str]:
        """转换为允许持久化的最小 JSON 结构。by AI.Coding"""
        payload = {"type": self.source_type.value, "id": str(self.id)}
        if self.field is not None:
            payload["field"] = self.field
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        return payload


class ClaimLike(Protocol):
    """定义发布校验所需的最小 claim 结构。by AI.Coding"""

    @property
    def source_refs(self) -> Sequence[Mapping[str, Any]]:
        """返回 claim 的来源引用。by AI.Coding"""
        ...


def validate_report_version(version: int) -> int:
    """校验报告版本从一开始单调编号。by AI.Coding"""
    if version < 1:
        raise InputError("报告版本必须大于或等于 1")
    return version


def parse_claim_source_ref(value: Mapping[str, Any]) -> ClaimSourceRef:
    """严格解析单个 claim 来源类型、UUID 和类型专属字段。by AI.Coding"""
    validate_no_sensitive_json_keys(value)
    raw_type = value.get("type")
    raw_id = value.get("id")
    if not isinstance(raw_type, str) or not isinstance(raw_id, str):
        raise InputError("claim 来源必须包含字符串 type 和 UUID id")
    try:
        source_type = ClaimSourceType(raw_type)
        source_id = uuid.UUID(raw_id)
    except (TypeError, ValueError) as exc:
        raise InputError("claim 来源必须包含受控 type 和有效 UUID id") from exc

    required_optional: dict[ClaimSourceType, tuple[set[str], set[str]]] = {
        ClaimSourceType.PRODUCT_SNAPSHOT: ({"type", "id", "field"}, set()),
        ClaimSourceType.BRAND_SOURCE: ({"type", "id", "field"}, set()),
        ClaimSourceType.ANALYSIS_METRIC: ({"type", "id"}, set()),
        ClaimSourceType.RAW_REVIEW: ({"type", "id", "evidence"}, set()),
    }
    required, optional = required_optional[source_type]
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise InputError(f"{source_type.value} 来源字段不符合白名单结构")

    field = value.get("field")
    evidence = value.get("evidence")
    if field is not None and (not isinstance(field, str) or not field.strip()):
        raise InputError("claim 来源 field 必须是非空字符串")
    if evidence is not None and (not isinstance(evidence, str) or not evidence):
        raise InputError("评论来源 evidence 必须是非空字符串")
    return ClaimSourceRef(source_type, source_id, field=field, evidence=evidence)


def validate_claim_source_refs(source_refs: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """校验 claim 至少绑定一个严格且受控的来源引用。by AI.Coding"""
    if not source_refs:
        raise InputError("报告结论必须至少关联一个来源引用")
    # 解析后重新生成白名单 payload，避免 Mapping 子类或额外对象进入 JSONB。
    return [parse_claim_source_ref(source_ref).to_payload() for source_ref in source_refs]


def validate_claim_sources_exist(
    source_refs: Sequence[Mapping[str, Any]],
    existing_refs: Iterable[ClaimSourceRef],
) -> None:
    """验证 claim 的每个来源均存在于仓储解析得到的引用集合。by AI.Coding"""
    existing_keys = {source_ref.key() for source_ref in existing_refs}
    for payload in source_refs:
        source_ref = parse_claim_source_ref(payload)
        if source_ref.key() not in existing_keys:
            reference_name = f"{source_ref.source_type.value}/{source_ref.id}"
            raise DomainConflictError(f"claim 来源不存在或与持久化证据不一致：{reference_name}")


def validate_report_publish(
    *,
    status: ReportStatus,
    claims: Sequence[ClaimLike],
    existing_refs: Iterable[ClaimSourceRef],
) -> ReportStatus:
    """在 completed/partial 发布前逐 claim 验证来源结构和存在性。by AI.Coding"""
    if status not in {ReportStatus.COMPLETED, ReportStatus.PARTIAL}:
        return status
    if not claims:
        raise DomainConflictError("可发布报告必须至少包含一个 claim")
    # 发布门禁逐条执行，任何无效引用都会阻止状态进入已发布结果。
    existing = tuple(existing_refs)
    for claim in claims:
        validate_claim_source_refs(claim.source_refs)
        validate_claim_sources_exist(claim.source_refs, existing)
    return status
