from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, Literal, Protocol, TypeVar
from uuid import UUID

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class StructuredLLMRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    purpose: str
    messages: tuple[BaseMessage, ...]
    trace_id: str
    prompt_version: str = "v1"
    timeout_seconds: float = Field(default=10, gt=0, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class StructuredLLMResult(BaseModel, Generic[ResponseT]):
    response: ResponseT
    provider: str
    model: str
    usage: TokenUsage
    latency_ms: int
    attempts: int
    audit_event_id: UUID


class LLMAuditEvent(BaseModel):
    event_id: UUID
    occurred_at: datetime
    purpose: str
    provider: str
    model: str
    trace_id: str
    prompt_version: str
    status: Literal["success", "error"]
    latency_ms: int
    attempts: int
    usage: TokenUsage
    error_code: str | None = None

    @classmethod
    def now(cls, **values: Any) -> LLMAuditEvent:
        return cls(occurred_at=datetime.now(UTC), **values)


class LLMAuditSink(Protocol):
    async def record(self, event: LLMAuditEvent) -> None: ...
