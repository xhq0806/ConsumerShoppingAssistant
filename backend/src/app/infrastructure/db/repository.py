from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model_type: type[ModelT]) -> None:
        self._session = session
        self._model_type = model_type

    def add(self, entity: ModelT) -> None:
        self._session.add(entity)

    async def get(self, entity_id: object) -> ModelT | None:
        return await self._session.get(self._model_type, entity_id)

    async def list(self) -> list[ModelT]:
        result = await self._session.scalars(select(self._model_type))
        return list(result)

    async def flush(self) -> None:
        await self._session.flush()
