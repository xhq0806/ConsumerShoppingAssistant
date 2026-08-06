import pytest
from conftest import migrated_postgres
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_migration_and_transaction_rollback() -> None:
    """验证临时数据库迁移和异步事务可用且不污染全局配置。by AI.Coding"""
    with migrated_postgres("head") as database:
        engine = create_async_engine(database.async_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            assert await session.scalar(text("SELECT 1")) == 1
            await session.rollback()
        await engine.dispose()
