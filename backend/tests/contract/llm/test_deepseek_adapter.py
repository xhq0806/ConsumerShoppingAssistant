"""DeepSeek Chat Completions Adapter HTTP 与脱敏契约测试。by AI.Coding"""

from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import (
    LLMAuthenticationError,
    LLMQuotaExhaustedError,
    LLMRequestInvalidError,
)
from app.providers.llm.audit import InMemoryLLMAuditSink
from app.providers.llm.base import StructuredLLMRequest
from app.providers.llm.deepseek_smoke import run_deepseek_smoke
from app.providers.llm.factory import create_llm_gateway


class Answer(BaseModel):
    """定义 DeepSeek 契约测试的最小结构化响应。by AI.Coding"""

    status: str


def _settings() -> Settings:
    """创建不读取本地 .env 的 DeepSeek 测试配置。by AI.Coding"""
    return Settings(
        _env_file=None,
        llm_provider="deepseek",
        deepseek_api_key="sk-deepseek-test-secret",
    )


def _success_response(content: str = '{"status":"ok"}') -> httpx.Response:
    """创建包含 usage 和思考内容的受控成功响应。by AI.Coding"""
    return httpx.Response(
        200,
        headers={"x-request-id": "request-1"},
        json={
            "id": "chatcmpl-1",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "reasoning_content": "不得进入结果或审计的思考正文",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        },
    )


@pytest.mark.asyncio
async def test_analysis_profile_uses_chat_json_and_disables_thinking() -> None:
    """评论分析 profile 使用 V4 Flash、JSON Output 和关闭思考。by AI.Coding"""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return _success_response()

    sink = InMemoryLLMAuditSink()
    gateway = create_llm_gateway(
        _settings(),
        sink,
        profile="analysis",
        transport=httpx.MockTransport(handler),
    )
    result = await gateway.invoke_structured(
        StructuredLLMRequest(
            purpose="review_annotation",
            messages=(
                SystemMessage(content="按指定字段分类。"),
                HumanMessage(content="评论正文"),
            ),
            trace_id="trace-analysis",
            max_retries=0,
        ),
        Answer,
    )

    body = captured["body"]
    assert isinstance(body, dict)
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer sk-deepseek-test-secret"
    assert body["model"] == "deepseek-v4-flash"
    assert body["stream"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in body
    assert body["messages"][0]["content"].find("JSON") >= 0
    assert result.response.status == "ok"
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
    assert result.usage.total_tokens == 18
    assert "思考正文" not in result.model_dump_json()
    assert sink.events[0].provider == "deepseek"
    assert sink.events[0].model == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_report_profile_enables_high_effort_thinking() -> None:
    """报告 profile 使用 V4 Pro 和 high 思考强度。by AI.Coding"""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _success_response()

    gateway = create_llm_gateway(
        _settings(),
        InMemoryLLMAuditSink(),
        profile="report",
        transport=httpx.MockTransport(handler),
    )
    await gateway.invoke_structured(
        StructuredLLMRequest(
            purpose="purchase_report",
            messages=(HumanMessage(content="综合比较"),),
            trace_id="trace-report",
            max_retries=0,
        ),
        Answer,
    )

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-v4-pro"
    assert body["thinking"] == {"type": "enabled"}
    assert body["reasoning_effort"] == "high"
    assert body["max_tokens"] == 8000


@pytest.mark.asyncio
async def test_empty_deepseek_content_retries_then_succeeds() -> None:
    """DeepSeek 空 content 经过 Gateway 重试后接受有效 JSON。by AI.Coding"""
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _success_response("" if calls == 1 else '{"status":"recovered"}')

    sink = InMemoryLLMAuditSink()
    gateway = create_llm_gateway(
        _settings(),
        sink,
        transport=httpx.MockTransport(handler),
    )
    result = await gateway.invoke_structured(
        StructuredLLMRequest(
            purpose="empty_retry",
            messages=(HumanMessage(content="返回 JSON"),),
            trace_id="trace-empty",
            max_retries=1,
        ),
        Answer,
    )

    assert calls == 2
    assert result.attempts == 2
    assert result.response.status == "recovered"
    assert len(sink.events) == 1


@pytest.mark.asyncio
async def test_authentication_failure_is_not_retried_or_leaked_to_audit() -> None:
    """鉴权失败只调用一次，审计不包含 Key、Prompt 或响应正文。by AI.Coding"""
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            401,
            json={"error": {"message": "server-secret-response-body"}},
        )

    sink = InMemoryLLMAuditSink()
    gateway = create_llm_gateway(
        _settings(),
        sink,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMAuthenticationError):
        await gateway.invoke_structured(
            StructuredLLMRequest(
                purpose="auth_failure",
                messages=(HumanMessage(content="private-prompt-body"),),
                trace_id="trace-auth",
                max_retries=3,
            ),
            Answer,
        )

    assert calls == 1
    serialized = sink.events[0].model_dump_json()
    assert sink.events[0].attempts == 1
    assert sink.events[0].error_code == "LLM_AUTHENTICATION_ERROR"
    assert "sk-deepseek-test-secret" not in serialized
    assert "private-prompt-body" not in serialized
    assert "server-secret-response-body" not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type", "error_code"),
    [
        (400, LLMRequestInvalidError, "LLM_REQUEST_INVALID"),
        (402, LLMQuotaExhaustedError, "LLM_QUOTA_EXHAUSTED"),
    ],
)
async def test_non_retryable_deepseek_client_errors_are_audited_once(
    status_code: int,
    error_type: type[Exception],
    error_code: str,
) -> None:
    """无效请求和额度不足不执行无意义重试。by AI.Coding"""
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json={"error": {"message": "hidden"}})

    sink = InMemoryLLMAuditSink()
    gateway = create_llm_gateway(
        _settings(),
        sink,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(error_type):
        await gateway.invoke_structured(
            StructuredLLMRequest(
                purpose="client_error",
                messages=(HumanMessage(content="JSON"),),
                trace_id="trace-client-error",
                max_retries=3,
            ),
            Answer,
        )

    assert calls == 1
    assert sink.events[0].attempts == 1
    assert sink.events[0].error_code == error_code


@pytest.mark.asyncio
async def test_deepseek_smoke_uses_analysis_profile_without_exposing_key() -> None:
    """Smoke 命令复用 analysis profile 并返回最小连接摘要。by AI.Coding"""
    captured_authorization = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_authorization
        captured_authorization = request.headers["Authorization"]
        return _success_response()

    result = await run_deepseek_smoke(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    assert captured_authorization == "Bearer sk-deepseek-test-secret"
    assert result.response.status == "ok"
    assert result.provider == "deepseek"
    assert "sk-deepseek-test-secret" not in result.model_dump_json()
