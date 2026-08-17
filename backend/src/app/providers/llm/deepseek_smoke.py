"""DeepSeek 配置完成后的最小真实 API 连通性检查。by AI.Coding"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

import httpx
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.providers.llm.audit import InMemoryLLMAuditSink
from app.providers.llm.base import (
    StructuredLLMRequest,
    StructuredLLMResult,
)
from app.providers.llm.factory import create_llm_gateway


class DeepSeekSmokeResponse(BaseModel):
    """定义连通性检查期望的最小 JSON。by AI.Coding"""

    status: Literal["ok"]


async def run_deepseek_smoke(
    settings: Settings,
    *,
    transport: httpx.MockTransport | None = None,
) -> StructuredLLMResult[DeepSeekSmokeResponse]:
    """调用 analysis profile 并返回不包含正文的结构化结果。by AI.Coding"""
    if settings.llm_provider != "deepseek":
        raise RuntimeError("请先设置 LLM_PROVIDER=deepseek")
    gateway = create_llm_gateway(
        settings,
        InMemoryLLMAuditSink(),
        profile="analysis",
        transport=transport,
    )
    return await gateway.invoke_structured(
        StructuredLLMRequest(
            purpose="deepseek_connectivity_check",
            messages=(
                HumanMessage(content='请返回 JSON 对象：{"status":"ok"}，不要输出其他内容。'),
            ),
            trace_id="deepseek-smoke",
            max_retries=0,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
        DeepSeekSmokeResponse,
    )


def main() -> None:
    """执行 smoke 并只打印非敏感连接摘要。by AI.Coding"""
    result = asyncio.run(run_deepseek_smoke(get_settings()))
    print(
        json.dumps(
            {
                "status": result.response.status,
                "provider": result.provider,
                "model": result.model,
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "latency_ms": result.latency_ms,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
