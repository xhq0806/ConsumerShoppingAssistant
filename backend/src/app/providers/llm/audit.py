from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.providers.llm.base import LLMAuditEvent


@dataclass
class InMemoryLLMAuditSink:
    events: list[LLMAuditEvent] = field(default_factory=list)

    async def record(self, event: LLMAuditEvent) -> None:
        self.events.append(event)


class StructuredLogLLMAuditSink:
    async def record(self, event: LLMAuditEvent) -> None:
        get_logger(component="llm_audit").info(
            "llm_call",
            **event.model_dump(mode="json"),
        )
