"""对比任务专用仓储查询。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.comparisons import ComparisonStatus
from app.infrastructure.db.models import (
    ComparisonProduct,
    ComparisonTask,
    ProductSku,
    ProductSnapshot,
    TaskEvent,
)
from app.infrastructure.db.repository import Repository
from app.providers.commerce.dto import NormalizedProductUrl, ProductDTO, SkuDTO


class ComparisonRepository(Repository[ComparisonTask]):
    """封装对比任务聚合查询且不提交事务。by AI.Coding"""

    def __init__(self, session: AsyncSession) -> None:
        """绑定异步会话和任务模型。by AI.Coding"""
        super().__init__(session, ComparisonTask)

    def add_candidate_from_dto(
        self, *, comparison_id: uuid.UUID, position: int, product_url: NormalizedProductUrl
    ) -> ComparisonProduct:
        """通过规范化 URL DTO 创建并加入候选商品。by AI.Coding"""
        candidate = ComparisonProduct._from_normalized_url(
            comparison_id=comparison_id,
            position=position,
            product_url=product_url,
        )
        self._session.add(candidate)
        return candidate

    def add_snapshot_from_dto(
        self, *, comparison_product_id: uuid.UUID, product: ProductDTO
    ) -> ProductSnapshot:
        """通过 ProductDTO 创建并加入事实快照。by AI.Coding"""
        snapshot = ProductSnapshot._from_dto(
            comparison_product_id=comparison_product_id,
            product=product,
        )
        self._session.add(snapshot)
        return snapshot

    def add_sku_from_dto(self, *, comparison_product_id: uuid.UUID, sku: SkuDTO) -> ProductSku:
        """通过 SkuDTO 创建并加入候选 SKU。by AI.Coding"""
        model = ProductSku._from_dto(comparison_product_id=comparison_product_id, sku=sku)
        self._session.add(model)
        return model

    async def get_detail(self, comparison_id: uuid.UUID) -> ComparisonTask | None:
        """载入任务及其商品、SKU、快照和事件。by AI.Coding"""
        # 使用 selectinload 避免异步环境中的隐式懒加载。
        statement = (
            select(ComparisonTask)
            .where(ComparisonTask.id == comparison_id)
            .options(
                selectinload(ComparisonTask.products).selectinload(ComparisonProduct.skus),
                selectinload(ComparisonTask.products).selectinload(ComparisonProduct.snapshots),
                selectinload(ComparisonTask.events),
            )
        )
        result = await self._session.scalars(statement)
        return result.one_or_none()

    async def list_by_status(self, status: ComparisonStatus) -> list[ComparisonTask]:
        """按创建时间倒序查询指定状态任务。by AI.Coding"""
        result = await self._session.scalars(
            select(ComparisonTask)
            .where(ComparisonTask.status == status)
            .order_by(ComparisonTask.created_at.desc())
        )
        return list(result)

    async def list_events(self, comparison_id: uuid.UUID) -> list[TaskEvent]:
        """按时间正序读取任务事件。by AI.Coding"""
        result = await self._session.scalars(
            select(TaskEvent)
            .where(TaskEvent.comparison_id == comparison_id)
            .order_by(TaskEvent.created_at.asc())
        )
        return list(result)

    def transition(self, task: ComparisonTask, target: ComparisonStatus) -> None:
        """经实体赋值验证器更新任务状态，不执行 flush 或 commit。by AI.Coding"""
        # 实体赋值是唯一状态转换门禁，仓储不重复调用状态机造成二次转换校验。
        task.status = target
