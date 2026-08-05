from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.health import router as health_router
from app.api.middleware import TraceIdMiddleware
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.db.dependencies import dispose_database


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_database()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    application = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(TraceIdMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    return application


app = create_app()
