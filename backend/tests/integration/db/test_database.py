import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from alembic import command


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_migration_and_transaction_rollback() -> None:
    project_dir = Path(__file__).parents[3]
    with PostgresContainer("postgres:16-alpine") as postgres:
        sync_url = postgres.get_connection_url().replace("psycopg2", "psycopg")
        async_url = sync_url.replace("postgresql+psycopg", "postgresql+asyncpg")
        os.environ["DATABASE_URL_SYNC"] = sync_url
        os.environ["DATABASE_URL"] = async_url

        config = Config(str(project_dir / "alembic.ini"))
        config.set_main_option("script_location", str(project_dir / "alembic"))
        command.upgrade(config, "head")

        engine = create_async_engine(async_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            assert await session.scalar(text("SELECT 1")) == 1
            await session.rollback()
        await engine.dispose()
