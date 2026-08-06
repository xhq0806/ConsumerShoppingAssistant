"""T05 分析数据专用仓储查询。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models import AnalysisMetric, RawReview
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
