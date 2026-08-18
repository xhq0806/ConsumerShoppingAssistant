from collections.abc import Sequence
from typing import Literal

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.core.config import Settings
from app.providers.llm.base import LLMAuditSink
from app.providers.llm.deepseek import DeepSeekChatModel
from app.providers.llm.gateway import LLMGateway

LLMProfile = Literal["analysis", "report"]


def create_chat_model(
    settings: Settings,
    responses: Sequence[str] | None = None,
    *,
    profile: LLMProfile = "analysis",
    transport: httpx.MockTransport | None = None,
) -> BaseChatModel:
    """按配置创建 Fake 或 DeepSeek ChatModel。by AI.Coding"""
    if settings.llm_provider == "fake":
        return FakeListChatModel(responses=list(responses or ['{"status":"ok"}']))
    if responses is not None:
        raise ValueError("DeepSeek Provider 不接受 Fake responses")
    assert settings.deepseek_api_key is not None
    if profile == "analysis":
        return DeepSeekChatModel(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model_name=settings.deepseek_analysis_model,
            thinking="enabled" if settings.deepseek_analysis_thinking else "disabled",
            reasoning_effort=None,
            max_tokens=settings.deepseek_analysis_max_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
            transport=transport,
        )
    return DeepSeekChatModel(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model_name=settings.deepseek_report_model,
        thinking="enabled" if settings.deepseek_report_thinking else "disabled",
        reasoning_effort=(
            settings.deepseek_report_reasoning_effort if settings.deepseek_report_thinking else None
        ),
        max_tokens=settings.deepseek_report_max_tokens,
        timeout_seconds=settings.deepseek_report_timeout_seconds,
        transport=transport,
    )


def create_llm_gateway(
    settings: Settings,
    audit_sink: LLMAuditSink,
    *,
    profile: LLMProfile = "analysis",
    responses: Sequence[str] | None = None,
    transport: httpx.MockTransport | None = None,
) -> LLMGateway:
    """创建带 provider/model 审计标识的 LLMGateway。by AI.Coding"""
    model = create_chat_model(
        settings,
        responses,
        profile=profile,
        transport=transport,
    )
    model_name = (
        settings.llm_model
        if settings.llm_provider == "fake"
        else (
            settings.deepseek_analysis_model
            if profile == "analysis"
            else settings.deepseek_report_model
        )
    )
    return LLMGateway(
        model,
        audit_sink,
        provider=settings.llm_provider,
        model_name=model_name,
    )
