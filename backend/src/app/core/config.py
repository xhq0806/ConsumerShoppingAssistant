from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置，由 AI.Coding 维护环境变量的确定性解析规则。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Consumer Shopping Assistant"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://shopping:shopping@localhost:5432/shopping"
    database_url_sync: str = "postgresql+psycopg://shopping:shopping@localhost:5432/shopping"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    review_max_per_product: int = Field(default=500, ge=1, le=500)

    commerce_provider: Literal["fixture"] = "fixture"
    llm_provider: Literal["fake", "deepseek"] = "fake"
    llm_model: str = "fake-structured-model"
    llm_timeout_seconds: float = Field(default=10, gt=0, le=120)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_analysis_model: Literal["deepseek-v4-flash", "deepseek-v4-pro"] = "deepseek-v4-flash"
    deepseek_report_model: Literal["deepseek-v4-flash", "deepseek-v4-pro"] = "deepseek-v4-pro"
    deepseek_analysis_thinking: bool = False
    deepseek_report_thinking: bool = True
    deepseek_report_reasoning_effort: Literal["high", "max"] = "high"
    deepseek_analysis_max_tokens: int = Field(default=2000, ge=1)
    deepseek_report_max_tokens: int = Field(default=8000, ge=1)
    deepseek_report_timeout_seconds: float = Field(default=120, gt=0, le=120)
    deepseek_report_max_retries: int = Field(default=0, ge=0, le=2)
    taobao_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = (
        "item.taobao.com",
        "detail.tmall.com",
    )

    @field_validator("taobao_allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: object) -> object:
        """将逗号分隔的白名单解析为标准化 host 元组。"""
        # pydantic-settings 默认会把复杂类型环境变量当 JSON 解码；NoDecode 保留原串，
        # 再由这里兼容易读的逗号分隔配置，避免容器启动阶段先于 validator 失败。
        if isinstance(value, str):
            return tuple(host.strip().lower() for host in value.split(",") if host.strip())
        return value

    @field_validator("deepseek_base_url")
    @classmethod
    def validate_deepseek_base_url(cls, value: str) -> str:
        """只接受不含凭据的 HTTPS DeepSeek API 基础地址。by AI.Coding"""
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("DEEPSEEK_BASE_URL 必须是有效 HTTPS 地址")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("DEEPSEEK_BASE_URL 不能包含用户名或密码")
        return normalized

    @model_validator(mode="after")
    def validate_deepseek_credentials(self) -> Settings:
        """启用 DeepSeek 时要求提供非空 API Key，fake 模式允许留空。by AI.Coding"""
        if self.llm_provider != "deepseek":
            return self
        value = (
            ""
            if self.deepseek_api_key is None
            else self.deepseek_api_key.get_secret_value().strip()
        )
        if not value:
            raise ValueError("LLM_PROVIDER=deepseek 时必须配置 DEEPSEEK_API_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
