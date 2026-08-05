from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any, TypeVar
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from app.core.errors import LLMTimeoutError, StructuredOutputInvalidError
from app.providers.llm.base import (
    LLMAuditEvent,
    LLMAuditSink,
    StructuredLLMRequest,
    StructuredLLMResult,
    TokenUsage,
)

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class LLMGateway:
    def __init__(
        self,
        model: BaseChatModel,
        audit_sink: LLMAuditSink,
        *,
        provider: str,
        model_name: str,
    ) -> None:
        self._model = model
        self._audit_sink = audit_sink
        self._provider = provider
        self._model_name = model_name

    async def invoke_structured(
        self,
        request: StructuredLLMRequest,
        response_model: type[ResponseT],
    ) -> StructuredLLMResult[ResponseT]:
        started = perf_counter()
        attempts = 0
        last_error: Exception | None = None
        usage = TokenUsage()

        while attempts <= request.max_retries:
            attempts += 1
            try:
                message = await asyncio.wait_for(
                    self._model.ainvoke(list(request.messages)),
                    timeout=request.timeout_seconds,
                )
                response = self._parse_content(message.content, response_model)
                usage = self._extract_usage(message.response_metadata)
                return await self._success_result(
                    request=request,
                    response=response,
                    attempts=attempts,
                    started=started,
                    usage=usage,
                )
            except TimeoutError:
                last_error = LLMTimeoutError("模型调用超过配置的时间限制。")
                if attempts > request.max_retries:
                    break
                await asyncio.sleep(0)
            except (ValidationError, ValueError, TypeError) as exc:
                last_error = StructuredOutputInvalidError("模型返回内容不符合结构化契约。")
                last_error.__cause__ = exc
                if attempts > request.max_retries:
                    break
                await asyncio.sleep(0)

        assert last_error is not None
        latency_ms = round((perf_counter() - started) * 1000)
        event = LLMAuditEvent.now(
            event_id=uuid4(),
            purpose=request.purpose,
            provider=self._provider,
            model=self._model_name,
            trace_id=request.trace_id,
            prompt_version=request.prompt_version,
            status="error",
            latency_ms=latency_ms,
            attempts=attempts,
            usage=usage,
            error_code=getattr(last_error, "code", "LLM_ERROR"),
        )
        await self._audit_sink.record(event)
        raise last_error

    @staticmethod
    def _parse_content(content: Any, response_model: type[ResponseT]) -> ResponseT:
        if isinstance(content, str):
            return response_model.model_validate_json(content)
        if isinstance(content, dict):
            return response_model.model_validate(content)
        raise TypeError("不支持的模型响应内容类型")

    @staticmethod
    def _extract_usage(metadata: dict[str, Any]) -> TokenUsage:
        raw = metadata.get("token_usage") or metadata.get("usage_metadata") or {}
        return TokenUsage(
            input_tokens=raw.get("prompt_tokens") or raw.get("input_tokens"),
            output_tokens=raw.get("completion_tokens") or raw.get("output_tokens"),
            total_tokens=raw.get("total_tokens"),
        )

    async def _success_result(
        self,
        *,
        request: StructuredLLMRequest,
        response: ResponseT,
        attempts: int,
        started: float,
        usage: TokenUsage,
    ) -> StructuredLLMResult[ResponseT]:
        latency_ms = round((perf_counter() - started) * 1000)
        event = LLMAuditEvent.now(
            event_id=uuid4(),
            purpose=request.purpose,
            provider=self._provider,
            model=self._model_name,
            trace_id=request.trace_id,
            prompt_version=request.prompt_version,
            status="success",
            latency_ms=latency_ms,
            attempts=attempts,
            usage=usage,
            error_code=None,
        )
        await self._audit_sink.record(event)
        return StructuredLLMResult[ResponseT](
            response=response,
            provider=self._provider,
            model=self._model_name,
            usage=usage,
            latency_ms=latency_ms,
            attempts=attempts,
            audit_event_id=event.event_id,
        )
