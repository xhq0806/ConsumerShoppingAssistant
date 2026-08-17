"""品牌与维度共享目录专用仓储。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.brands import normalize_brand_name
from app.domain.dimensions import normalize_dimension_code, validate_registered_dimension
from app.infrastructure.db.models import (
    BrandProfile,
    DimensionDefinition,
    TaskDimension,
)


class CatalogRepository:
    """封装品牌和维度目录持久化操作且不提交事务。by AI.Coding"""

    def __init__(self, session: AsyncSession) -> None:
        """绑定由调用方管理事务的异步会话。by AI.Coding"""
        self._session = session

    def add_brand(self, brand: BrandProfile) -> None:
        """把品牌主档加入当前工作单元。by AI.Coding"""
        self._session.add(brand)

    def add_dimension(self, dimension: DimensionDefinition) -> None:
        """把维度定义加入当前工作单元。by AI.Coding"""
        self._session.add(dimension)

    async def get_brand_by_name(self, name: str) -> BrandProfile | None:
        """按确定性标准名载入品牌及全部字段来源。by AI.Coding"""
        result = await self._session.scalars(
            select(BrandProfile)
            .where(BrandProfile.normalized_name == normalize_brand_name(name))
            .options(selectinload(BrandProfile.sources))
        )
        return result.one_or_none()

    async def get_dimension_by_code(self, code: str) -> DimensionDefinition | None:
        """按稳定 code 查询已注册维度。by AI.Coding"""
        result = await self._session.scalars(
            select(DimensionDefinition).where(
                DimensionDefinition.code == normalize_dimension_code(code)
            )
        )
        return result.one_or_none()

    async def resolve_enabled_dimension(self, code: str) -> DimensionDefinition:
        """解析已注册且启用的维度，否则抛出领域冲突。by AI.Coding"""
        dimension = await self.get_dimension_by_code(code)
        return validate_registered_dimension(
            code,
            dimension,
            enabled=None if dimension is None else dimension.enabled,
        )

    async def list_enabled_dimensions(self, *, category: str | None) -> list[DimensionDefinition]:
        """按优先级列出通用或指定品类的启用维度。by AI.Coding"""
        category_filter = (
            DimensionDefinition.category.is_(None)
            if category is None
            else or_(
                DimensionDefinition.category.is_(None), DimensionDefinition.category == category
            )
        )
        result = await self._session.scalars(
            select(DimensionDefinition)
            .where(DimensionDefinition.enabled.is_(True), category_filter)
            .order_by(DimensionDefinition.default_priority.asc(), DimensionDefinition.code.asc())
        )
        return list(result)

    def add_task_dimension(self, task_dimension: TaskDimension) -> None:
        """把任务维度候选加入当前工作单元。by AI.Coding"""
        self._session.add(task_dimension)

    async def list_task_dimensions(self, comparison_id: uuid.UUID) -> list[TaskDimension]:
        """按重点顺序和目录优先级加载任务全部候选维度。by AI.Coding"""
        result = await self._session.scalars(
            select(TaskDimension)
            .where(TaskDimension.comparison_id == comparison_id)
            .options(selectinload(TaskDimension.dimension))
            .order_by(
                case((TaskDimension.selected.is_(True), 0), else_=1),
                TaskDimension.position.asc().nulls_last(),
                DimensionDefinition.default_priority.asc(),
                DimensionDefinition.code.asc(),
            )
            .join(TaskDimension.dimension)
        )
        return list(result)

    async def flush(self) -> None:
        """刷新当前目录变更但不执行 commit。by AI.Coding"""
        await self._session.flush()
