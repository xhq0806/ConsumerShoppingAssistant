"""DeepSeek Chat Completions 结构化 JSON Adapter。by AI.Coding"""

from __future__ import annotations

from typing import Any, Literal, cast

import httpx
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict, Field, PrivateAttr, SecretStr

from app.core.errors import (
    LLMAuthenticationError,
    LLMError,
    LLMProviderUnavailableError,
    LLMQuotaExhaustedError,
    LLMRateLimitedError,
    LLMRequestInvalidError,
    LLMTimeoutError,
    StructuredOutputInvalidError,
)

ThinkingMode = Literal["enabled", "disabled"]
ReasoningEffort = Literal["high", "max"]

_JSON_SYSTEM_INSTRUCTION = "你必须只输出一个合法 JSON 对象，不要输出 Markdown、代码围栏或额外解释。"


class DeepSeekChatModel(BaseChatModel):
    """通过 DeepSeek `/chat/completions` 返回 JSON 文本的 LangChain ChatModel。by AI.Coding"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    api_key: SecretStr = Field(exclude=True, repr=False)
    base_url: str
    model_name: str
    thinking: ThinkingMode = "disabled"
    reasoning_effort: ReasoningEffort | None = None
    max_tokens: int = Field(default=2000, ge=1)
    timeout_seconds: float = Field(default=10, gt=0, le=120)
    _transport: httpx.MockTransport | None = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        transport: httpx.MockTransport | None = None,
        **values: Any,
    ) -> None:
        """初始化可在测试中注入 MockTransport 的 DeepSeek 模型。by AI.Coding"""
        super().__init__(**values)
        self._transport = transport

    @property
    def _llm_type(self) -> str:
        """返回 LangChain 用于标识 Adapter 的稳定类型。by AI.Coding"""
        return "deepseek-chat-completions"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        """只暴露非敏感模型配置，不包含 API Key。by AI.Coding"""
        return {
            "base_url": self.base_url,
            "model_name": self.model_name,
            "thinking": self.thinking,
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": self.max_tokens,
        }

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """同步调用 DeepSeek，供 LangChain 同步入口兼容使用。by AI.Coding"""
        del run_manager, kwargs
        transport = cast(httpx.BaseTransport | None, self._transport)
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=transport) as client:
                response = client.post(
                    self._endpoint(),
                    headers=self._headers(),
                    json=self._request_body(messages, stop),
                )
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("DeepSeek API 请求超时。") from error
        except httpx.HTTPError as error:
            raise LLMProviderUnavailableError("DeepSeek API 暂时无法连接。") from error
        return self._to_chat_result(response)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """异步调用 DeepSeek Chat Completions。by AI.Coding"""
        del run_manager, kwargs
        transport = cast(httpx.AsyncBaseTransport | None, self._transport)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=transport,
            ) as client:
                response = await client.post(
                    self._endpoint(),
                    headers=self._headers(),
                    json=self._request_body(messages, stop),
                )
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("DeepSeek API 请求超时。") from error
        except httpx.HTTPError as error:
            raise LLMProviderUnavailableError("DeepSeek API 暂时无法连接。") from error
        return self._to_chat_result(response)

    def _request_body(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None,
    ) -> dict[str, Any]:
        """构造非流式 JSON Output 请求并按 profile 设置思考模式。by AI.Coding"""
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": _JSON_SYSTEM_INSTRUCTION},
                *(self._message_payload(message) for message in messages),
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_tokens,
            "thinking": {"type": self.thinking},
        }
        if stop:
            payload["stop"] = stop
        if self.thinking == "enabled" and self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        return payload

    @staticmethod
    def _message_payload(message: BaseMessage) -> dict[str, str]:
        """把当前项目允许的纯文本 LangChain 消息映射为 DeepSeek role。by AI.Coding"""
        if not isinstance(message.content, str):
            raise TypeError("DeepSeek Adapter 当前只支持纯文本消息")
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            raise TypeError(f"DeepSeek Adapter 不支持消息类型 {type(message).__name__}")
        return {"role": role, "content": message.content}

    def _to_chat_result(self, response: httpx.Response) -> ChatResult:
        """校验 HTTP/JSON 白名单并转换为 LangChain ChatResult。by AI.Coding"""
        self._raise_for_status(response)
        try:
            payload = response.json()
        except ValueError as error:
            raise StructuredOutputInvalidError("DeepSeek 返回了无效 JSON 响应。") from error
        if not isinstance(payload, dict):
            raise StructuredOutputInvalidError("DeepSeek 响应根节点不是对象。")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise StructuredOutputInvalidError("DeepSeek 响应缺少 choices。")
        first = choices[0]
        if not isinstance(first, dict):
            raise StructuredOutputInvalidError("DeepSeek choice 格式无效。")
        message = first.get("message")
        if not isinstance(message, dict):
            raise StructuredOutputInvalidError("DeepSeek 响应缺少 message。")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise StructuredOutputInvalidError("DeepSeek 返回了空结构化内容。")
        usage = payload.get("usage")
        token_usage = usage if isinstance(usage, dict) else {}
        ai_message = AIMessage(
            content=content,
            response_metadata={
                "token_usage": token_usage,
                "finish_reason": first.get("finish_reason"),
                "request_id": response.headers.get("x-request-id"),
            },
        )
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """把 DeepSeek HTTP 状态映射为不包含响应正文的受控错误。by AI.Coding"""
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            raise LLMAuthenticationError("DeepSeek API Key 无效或没有访问权限。")
        if response.status_code in {400, 422}:
            raise LLMRequestInvalidError("DeepSeek API 拒绝了当前请求参数。")
        if response.status_code == 402:
            raise LLMQuotaExhaustedError("DeepSeek 账户余额或额度不足。")
        if response.status_code == 429:
            raise LLMRateLimitedError("DeepSeek API 请求频率受限。")
        if response.status_code >= 500:
            raise LLMProviderUnavailableError("DeepSeek API 暂时不可用。")
        raise LLMError(f"DeepSeek API 请求失败，HTTP {response.status_code}。")

    def _headers(self) -> dict[str, str]:
        """构造仅用于 HTTP 请求的鉴权头，不进入日志和审计。by AI.Coding"""
        return {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _endpoint(self) -> str:
        """返回 DeepSeek Chat Completions 端点。by AI.Coding"""
        return f"{self.base_url.rstrip('/')}/chat/completions"
