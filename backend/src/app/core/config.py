from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
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

    commerce_provider: Literal["fixture"] = "fixture"
    llm_provider: Literal["fake"] = "fake"
    llm_model: str = "fake-structured-model"
    llm_timeout_seconds: float = Field(default=10, gt=0, le=120)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
