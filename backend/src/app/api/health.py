from fastapi import APIRouter, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.errors import ProviderUnavailableError
from app.infrastructure.db.dependencies import engine

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        redis = Redis.from_url(get_settings().redis_url)
        try:
            await redis.ping()
        finally:
            await redis.aclose()
    except Exception as exc:
        raise ProviderUnavailableError("服务依赖尚未就绪。") from exc
    return HealthResponse(status="ready")
