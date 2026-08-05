from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory

settings = get_settings()
engine: AsyncEngine = create_engine(settings)
session_factory: async_sessionmaker[AsyncSession] = create_session_factory(engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def dispose_database() -> None:
    await engine.dispose()
