from collections.abc import Mapping
from typing import Any


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    title = "服务内部错误"

    def __init__(
        self,
        detail: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.metadata = dict(metadata or {})


class InputError(AppError):
    status_code = 422
    code = "INVALID_INPUT"
    title = "输入不符合要求"


class DomainConflictError(AppError):
    status_code = 409
    code = "DOMAIN_CONFLICT"
    title = "当前状态存在冲突"


class ResourceNotFoundError(AppError):
    """表示对外可安全暴露的资源不存在错误。by AI.Coding"""

    status_code = 404
    code = "RESOURCE_NOT_FOUND"
    title = "资源不存在"


class ProviderError(AppError):
    status_code = 502
    code = "PROVIDER_ERROR"
    title = "外部数据服务错误"


class ProviderUnavailableError(ProviderError):
    status_code = 503
    code = "PROVIDER_UNAVAILABLE"
    title = "外部数据服务暂不可用"


class ProviderRateLimitedError(ProviderUnavailableError):
    code = "PROVIDER_RATE_LIMITED"
    title = "外部数据服务请求受限"


class ProviderNotFoundError(ProviderError):
    status_code = 404
    code = "PROVIDER_RESOURCE_NOT_FOUND"
    title = "外部资源不存在"


class ProviderInvalidResponseError(ProviderError):
    code = "PROVIDER_INVALID_RESPONSE"
    title = "外部数据响应无效"


class AnalysisDispatchError(AppError):
    """表示分析任务无法提交到异步队列。by AI.Coding"""

    status_code = 503
    code = "ANALYSIS_DISPATCH_UNAVAILABLE"
    title = "分析任务暂时无法排队"


class URLSecurityError(InputError):
    code = "UNSAFE_PRODUCT_URL"
    title = "商品链接不安全或不受支持"


class LLMError(AppError):
    status_code = 503
    code = "LLM_ERROR"
    title = "模型服务错误"
    retryable = True


class LLMTimeoutError(LLMError):
    code = "LLM_TIMEOUT"
    title = "模型服务超时"


class LLMAuthenticationError(LLMError):
    code = "LLM_AUTHENTICATION_ERROR"
    title = "模型服务鉴权失败"
    retryable = False


class LLMRequestInvalidError(LLMError):
    code = "LLM_REQUEST_INVALID"
    title = "模型请求参数无效"
    retryable = False


class LLMQuotaExhaustedError(LLMError):
    code = "LLM_QUOTA_EXHAUSTED"
    title = "模型服务额度不足"
    retryable = False


class LLMRateLimitedError(LLMError):
    code = "LLM_RATE_LIMITED"
    title = "模型服务请求受限"


class LLMProviderUnavailableError(LLMError):
    code = "LLM_PROVIDER_UNAVAILABLE"
    title = "模型服务暂不可用"


class StructuredOutputInvalidError(LLMError):
    code = "LLM_STRUCTURED_OUTPUT_INVALID"
    title = "模型结构化输出无效"
