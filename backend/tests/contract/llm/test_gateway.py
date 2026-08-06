import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import StructuredOutputInvalidError
from app.providers.llm.audit import InMemoryLLMAuditSink
from app.providers.llm.base import StructuredLLMRequest
from app.providers.llm.factory import create_chat_model
from app.providers.llm.gateway import LLMGateway


class Answer(BaseModel):
    status: str


@pytest.mark.asyncio
async def test_gateway_returns_validated_structured_result_and_audit() -> None:
    settings = Settings()
    sink = InMemoryLLMAuditSink()
    gateway = LLMGateway(
        create_chat_model(settings, ['{"status":"ok"}']),
        sink,
        provider="fake",
        model_name=settings.llm_model,
    )
    result = await gateway.invoke_structured(
        StructuredLLMRequest(
            purpose="contract_test",
            messages=(HumanMessage(content="返回结构化结果"),),
            trace_id="trace-1",
            max_retries=0,
        ),
        Answer,
    )
    assert result.response.status == "ok"
    assert result.attempts == 1
    assert sink.events[0].attempts == 1
    assert sink.events[0].status == "success"
    assert sink.events[0].trace_id == "trace-1"


@pytest.mark.asyncio
async def test_gateway_retries_invalid_structured_output() -> None:
    settings = Settings()
    sink = InMemoryLLMAuditSink()
    gateway = LLMGateway(
        create_chat_model(settings, ["not-json", '{"status":"ok"}']),
        sink,
        provider="fake",
        model_name=settings.llm_model,
    )
    result = await gateway.invoke_structured(
        StructuredLLMRequest(
            purpose="retry_test",
            messages=(HumanMessage(content="返回结构化结果"),),
            trace_id="trace-2",
            max_retries=1,
        ),
        Answer,
    )
    assert result.attempts == 2
    assert len(sink.events) == 1


@pytest.mark.asyncio
async def test_gateway_audits_exhausted_invalid_output_without_body() -> None:
    settings = Settings()
    sink = InMemoryLLMAuditSink()
    gateway = LLMGateway(
        create_chat_model(settings, ["secret-response-body"]),
        sink,
        provider="fake",
        model_name=settings.llm_model,
    )
    with pytest.raises(StructuredOutputInvalidError):
        await gateway.invoke_structured(
            StructuredLLMRequest(
                purpose="error_test",
                messages=(HumanMessage(content="private-prompt-body"),),
                trace_id="trace-3",
                max_retries=0,
            ),
            Answer,
        )
    serialized = sink.events[0].model_dump_json()
    assert "private-prompt-body" not in serialized
    assert "secret-response-body" not in serialized
