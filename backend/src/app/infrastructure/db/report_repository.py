"""T05 报告数据专用仓储查询。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.reports import (
    ClaimSourceRef,
    ClaimSourceType,
    ReportStatus,
    parse_claim_source_ref,
    validate_report_publish,
)
from app.infrastructure.db.models import (
    AnalysisMetric,
    BrandSource,
    ComparisonReport,
    ProductSnapshot,
    RawReview,
)
from app.infrastructure.db.repository import Repository


class ReportRepository(Repository[ComparisonReport]):
    """封装版本报告与结论查询且不提交事务。by AI.Coding"""

    def __init__(self, session: AsyncSession) -> None:
        """绑定异步会话和报告模型。by AI.Coding"""
        super().__init__(session, ComparisonReport)

    async def _existing_snapshot_refs(self, refs: list[ClaimSourceRef]) -> set[ClaimSourceRef]:
        """解析存在且字段有效的商品快照引用。by AI.Coding"""
        rows = list(
            await self._session.scalars(
                select(ProductSnapshot).where(ProductSnapshot.id.in_([ref.id for ref in refs]))
            )
        )
        ids = {row.id for row in rows}
        return {
            ref
            for ref in refs
            if ref.id in ids
            and ref.field is not None
            and ref.field in ProductSnapshot.__table__.columns
        }

    async def _existing_brand_source_refs(self, refs: list[ClaimSourceRef]) -> set[ClaimSourceRef]:
        """解析存在且字段匹配的品牌来源引用。by AI.Coding"""
        rows = list(
            await self._session.scalars(
                select(BrandSource).where(BrandSource.id.in_([ref.id for ref in refs]))
            )
        )
        fields_by_id = {row.id: row.field_name.value for row in rows}
        return {ref for ref in refs if fields_by_id.get(ref.id) == ref.field}

    async def _existing_metric_refs(self, refs: list[ClaimSourceRef]) -> set[ClaimSourceRef]:
        """解析存在的确定性指标引用。by AI.Coding"""
        ids = set(
            await self._session.scalars(
                select(AnalysisMetric.id).where(AnalysisMetric.id.in_([ref.id for ref in refs]))
            )
        )
        return {ref for ref in refs if ref.id in ids}

    async def _existing_review_refs(self, refs: list[ClaimSourceRef]) -> set[ClaimSourceRef]:
        """解析存在且 evidence 为正文连续子串的评论引用。by AI.Coding"""
        rows = list(
            await self._session.scalars(
                select(RawReview).where(RawReview.id.in_([ref.id for ref in refs]))
            )
        )
        content_by_id = {row.id: row.content for row in rows}
        return {
            ref
            for ref in refs
            if ref.evidence is not None and ref.evidence in content_by_id.get(ref.id, "")
        }

    async def resolve_existing_claim_sources(
        self, source_refs: list[dict[str, object]]
    ) -> set[ClaimSourceRef]:
        """查询并返回确实存在且与引用字段一致的 claim 来源集合。by AI.Coding"""
        parsed = [parse_claim_source_ref(source_ref) for source_ref in source_refs]
        # 按受控类型分组调用明确类型的查询辅助，避免动态模型破坏静态检查。
        grouped = {
            source_type: [ref for ref in parsed if ref.source_type is source_type]
            for source_type in ClaimSourceType
        }
        resolved: set[ClaimSourceRef] = set()
        snapshot_refs = grouped[ClaimSourceType.PRODUCT_SNAPSHOT]
        brand_refs = grouped[ClaimSourceType.BRAND_SOURCE]
        resolved.update(await self._existing_snapshot_refs(snapshot_refs))
        resolved.update(await self._existing_brand_source_refs(brand_refs))
        resolved.update(await self._existing_metric_refs(grouped[ClaimSourceType.ANALYSIS_METRIC]))
        resolved.update(await self._existing_review_refs(grouped[ClaimSourceType.RAW_REVIEW]))
        return resolved

    async def publish(self, report: ComparisonReport, target: ReportStatus) -> None:
        """解析来源并通过门禁后设置 completed/partial 状态且不提交事务。by AI.Coding"""
        payloads = [source_ref for claim in report.claims for source_ref in claim.source_refs]
        existing = await self.resolve_existing_claim_sources(payloads)
        report.status = validate_report_publish(
            status=target,
            claims=report.claims,
            existing_refs=existing,
        )

    async def get_version(
        self, *, comparison_id: uuid.UUID, version: int
    ) -> ComparisonReport | None:
        """按任务和版本读取报告及全部结论。by AI.Coding"""
        result = await self._session.scalars(
            select(ComparisonReport)
            .where(
                ComparisonReport.comparison_id == comparison_id,
                ComparisonReport.version == version,
            )
            .options(selectinload(ComparisonReport.claims))
        )
        return result.one_or_none()

    async def get_latest(self, comparison_id: uuid.UUID) -> ComparisonReport | None:
        """读取任务最新版本报告及全部结论。by AI.Coding"""
        result = await self._session.scalars(
            select(ComparisonReport)
            .where(ComparisonReport.comparison_id == comparison_id)
            .options(selectinload(ComparisonReport.claims))
            .order_by(ComparisonReport.version.desc())
            .limit(1)
        )
        return result.one_or_none()
