"""集成测试临时 PostgreSQL 与 Alembic 配置夹具。by AI.Coding"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

from alembic import command
from app.core.config import get_settings


@dataclass(frozen=True)
class TemporaryDatabase:
    """保存单个临时数据库的连接与迁移配置。by AI.Coding"""

    sync_url: str
    async_url: str
    alembic_config: Config


@contextmanager
def migrated_postgres(target: str) -> Iterator[TemporaryDatabase]:
    """启动隔离 PostgreSQL，迁移到目标版本，并恢复环境与配置缓存。by AI.Coding"""
    project_dir = Path(__file__).parents[3]
    previous_sync = os.environ.get("DATABASE_URL_SYNC")
    previous_async = os.environ.get("DATABASE_URL")
    try:
        with PostgresContainer("postgres:16-alpine") as postgres:
            sync_url = postgres.get_connection_url().replace("psycopg2", "psycopg")
            async_url = sync_url.replace("postgresql+psycopg", "postgresql+asyncpg")
            # 每个容器都覆盖环境并清缓存，避免测试收集或执行顺序污染配置。
            os.environ["DATABASE_URL_SYNC"] = sync_url
            os.environ["DATABASE_URL"] = async_url
            get_settings.cache_clear()
            config = Config(str(project_dir / "alembic.ini"))
            config.set_main_option("script_location", str(project_dir / "alembic"))
            command.upgrade(config, target)
            yield TemporaryDatabase(sync_url, async_url, config)
    finally:
        # 无论测试成功或失败都恢复调用前环境，并使后续读取不命中旧容器缓存。
        if previous_sync is None:
            os.environ.pop("DATABASE_URL_SYNC", None)
        else:
            os.environ["DATABASE_URL_SYNC"] = previous_sync
        if previous_async is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_async
        get_settings.cache_clear()
