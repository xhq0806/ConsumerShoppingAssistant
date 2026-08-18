"""T05 模型运行专用仓储与 SQLAlchemy 审计 sink。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.model_runs import ModelRunStatus
from app.infrastructure.db.models import ModelRun
from app.infrastructure.db.repository import Repository
from app.providers.llm.base import LLMAuditEvent


class ModelRunRepository(Repository[ModelRun]):
    """封装模型运行安全元数据查询且不提交事务。by AI.Coding"""

    def __init__(self, session: AsyncSession) -> None:
        """绑定异步会话和模型运行模型。by AI.Coding"""
        super().__init__(session, ModelRun)

    async def get_by_event_id(self, event_id: uuid.UUID) -> ModelRun | None:
        """按 Gateway 审计事件标识读取唯一运行记录。by AI.Coding"""
        result = await self._session.scalars(select(ModelRun).where(ModelRun.event_id == event_id))
        return result.one_or_none()

    async def list_for_comparison(self, comparison_id: uuid.UUID) -> list[ModelRun]:
        """按发生时间读取任务关联的模型运行。by AI.Coding"""
        result = await self._session.scalars(
            select(ModelRun)
            .where(ModelRun.comparison_id == comparison_id)
            .order_by(ModelRun.occurred_at.asc())
        )
        return list(result)

    def add_from_audit_event(
        self,
        event: LLMAuditEvent,
        *,
        comparison_id: uuid.UUID | None,
    ) -> ModelRun:
        """从白名单审计事件创建模型运行记录且不提交事务。by AI.Coding"""
        model = ModelRun(
            event_id=event.event_id,
            comparison_id=comparison_id,
            purpose=event.purpose,
            provider=event.provider,
            model=event.model,
            trace_id=event.trace_id,
            prompt_version=event.prompt_version,
            status=ModelRunStatus(event.status),
            error_code=event.error_code,
            latency_ms=event.latency_ms,
            attempts=event.attempts,
            input_tokens=event.usage.input_tokens,
            output_tokens=event.usage.output_tokens,
            total_tokens=event.usage.total_tokens,
            occurred_at=event.occurred_at,
        )
        self._session.add(model)
        return model


class SQLAlchemyLLMAuditSink:
    """把 LLMAuditEvent 白名单安全元数据加入调用方事务。by AI.Coding"""

    def __init__(self, session: AsyncSession, *, comparison_id: uuid.UUID | None = None) -> None:
        """绑定异步会话和可选任务关联，不接管事务提交。by AI.Coding"""
        self._session = session
        self._comparison_id = comparison_id

    async def record(self, event: LLMAuditEvent) -> None:
        """持久化事件安全字段并 flush，但不 commit。by AI.Coding"""
        # 显式逐字段映射，确保未来事件增加 prompt/messages/response 等字段时不会被透传。
        ModelRunRepository(self._session).add_from_audit_event(
            event,
            comparison_id=self._comparison_id,
        )
        await self._session.flush()
