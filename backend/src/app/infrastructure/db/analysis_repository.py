"""T05 分析数据专用仓储查询。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.metrics.calculation import CalculatedReviewMetric
from app.domain.reviews.annotation import ValidatedReviewAnnotation
from app.infrastructure.db.models import (
    AnalysisMetric,
    ComparisonProduct,
    RawReview,
    ReviewAnnotation,
)
from app.infrastructure.db.repository import Repository
from app.providers.commerce.dto import ReviewDTO


class AnalysisRepository(Repository[RawReview]):
    """封装评论与确定性指标持久化且不提交事务。by AI.Coding"""

    def __init__(self, session: AsyncSession) -> None:
        """绑定异步会话和原始评论模型。by AI.Coding"""
        super().__init__(session, RawReview)

    def add_review_from_dto(
        self, *, comparison_product_id: uuid.UUID, review: ReviewDTO
    ) -> RawReview:
        """通过 ReviewDTO 创建并加入最小原始评论记录。by AI.Coding"""
        model = RawReview._from_dto(comparison_product_id=comparison_product_id, review=review)
        self._session.add(model)
        return model

    async def list_reviews(self, comparison_product_id: uuid.UUID) -> list[RawReview]:
        """按评论时间读取商品评论及其维度注解。by AI.Coding"""
        result = await self._session.scalars(
            select(RawReview)
            .where(RawReview.comparison_product_id == comparison_product_id)
            .options(selectinload(RawReview.annotations))
            .order_by(RawReview.reviewed_at.asc())
        )
        return list(result)

    async def list_metrics(self, comparison_id: uuid.UUID) -> list[AnalysisMetric]:
        """读取任务级与商品级的全部确定性指标。by AI.Coding"""
        result = await self._session.scalars(
            select(AnalysisMetric)
            .where(AnalysisMetric.comparison_id == comparison_id)
            .order_by(AnalysisMetric.metric_type.asc())
        )
        return list(result)

    async def count_reviews_for_comparison(self, comparison_id: uuid.UUID) -> int:
        """统计任务全部候选已持久化的有效评论数。by AI.Coding"""
        count = await self._session.scalar(
            select(func.count())
            .select_from(RawReview)
            .join(ComparisonProduct, ComparisonProduct.id == RawReview.comparison_product_id)
            .where(ComparisonProduct.comparison_id == comparison_id)
        )
        return int(count or 0)

    async def list_reviews_for_comparison(self, comparison_id: uuid.UUID) -> list[RawReview]:
        """按商品位置、评论时间和 UUID 稳定读取任务评论及现有注解。by AI.Coding"""
        result = await self._session.scalars(
            select(RawReview)
            .join(ComparisonProduct, ComparisonProduct.id == RawReview.comparison_product_id)
            .where(ComparisonProduct.comparison_id == comparison_id)
            .options(selectinload(RawReview.annotations))
            .order_by(
                ComparisonProduct.position.asc(),
                RawReview.reviewed_at.asc(),
                RawReview.id.asc(),
            )
        )
        return list(result)

    async def list_annotations_for_comparison(
        self,
        comparison_id: uuid.UUID,
    ) -> list[ReviewAnnotation]:
        """稳定读取任务全部评论注解。by AI.Coding"""
        result = await self._session.scalars(
            select(ReviewAnnotation)
            .join(RawReview, RawReview.id == ReviewAnnotation.review_id)
            .join(ComparisonProduct, ComparisonProduct.id == RawReview.comparison_product_id)
            .where(ComparisonProduct.comparison_id == comparison_id)
            .order_by(
                ComparisonProduct.position.asc(),
                RawReview.reviewed_at.asc(),
                ReviewAnnotation.dimension_id.asc(),
            )
        )
        return list(result)

    def add_annotations(
        self,
        annotations: Sequence[ValidatedReviewAnnotation],
        *,
        model_run_id: uuid.UUID,
    ) -> list[ReviewAnnotation]:
        """批量加入已通过语义校验的评论注解。by AI.Coding"""
        models = [
            ReviewAnnotation(
                review_id=annotation.review_id,
                dimension_id=annotation.dimension_id,
                sentiment=annotation.sentiment,
                confidence=annotation.confidence,
                evidence=annotation.evidence,
                model_run_id=model_run_id,
            )
            for annotation in annotations
        ]
        self._session.add_all(models)
        return models

    async def replace_review_metrics(
        self,
        *,
        comparison_id: uuid.UUID,
        metrics: Sequence[CalculatedReviewMetric],
    ) -> list[AnalysisMetric]:
        """删除任务旧指标并按当前持久化注解完整重建。by AI.Coding"""
        await self._session.execute(
            delete(AnalysisMetric).where(AnalysisMetric.comparison_id == comparison_id)
        )
        models = [
            AnalysisMetric(
                comparison_id=metric.comparison_id,
                comparison_product_id=metric.comparison_product_id,
                dimension_id=metric.dimension_id,
                metric_type=metric.metric_type,
                numeric_value=metric.numeric_value,
                sample_size=metric.sample_size,
                confidence=metric.confidence,
                source_refs=[_metric_source_ref(metric)],
            )
            for metric in metrics
        ]
        self._session.add_all(models)
        return models

    async def count_annotations_for_comparison(self, comparison_id: uuid.UUID) -> int:
        """统计任务已持久化的维度注解数。by AI.Coding"""
        count = await self._session.scalar(
            select(func.count())
            .select_from(ReviewAnnotation)
            .join(RawReview, RawReview.id == ReviewAnnotation.review_id)
            .join(ComparisonProduct, ComparisonProduct.id == RawReview.comparison_product_id)
            .where(ComparisonProduct.comparison_id == comparison_id)
        )
        return int(count or 0)

    async def count_annotated_reviews_for_comparison(self, comparison_id: uuid.UUID) -> int:
        """统计至少拥有一个维度注解的任务评论数。by AI.Coding"""
        count = await self._session.scalar(
            select(func.count(func.distinct(ReviewAnnotation.review_id)))
            .join(RawReview, RawReview.id == ReviewAnnotation.review_id)
            .join(ComparisonProduct, ComparisonProduct.id == RawReview.comparison_product_id)
            .where(ComparisonProduct.comparison_id == comparison_id)
        )
        return int(count or 0)

    async def count_metrics_for_comparison(self, comparison_id: uuid.UUID) -> int:
        """统计任务当前确定性指标记录数。by AI.Coding"""
        count = await self._session.scalar(
            select(func.count())
            .select_from(AnalysisMetric)
            .where(AnalysisMetric.comparison_id == comparison_id)
        )
        return int(count or 0)


def _metric_source_ref(metric: CalculatedReviewMetric) -> dict[str, Any]:
    """构造不含正文的可复算指标输入引用。by AI.Coding"""
    return {
        "type": "review_annotation_inputs",
        "review_ids": [str(review_id) for review_id in metric.review_ids],
        "annotation_ids": [str(annotation_id) for annotation_id in metric.annotation_ids],
    }
