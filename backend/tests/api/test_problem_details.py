import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.errors import DomainConflictError, ProviderUnavailableError
from app.main import create_app


@pytest.fixture
def test_app():
    app = create_app()
    router = APIRouter(prefix="/test")

    @router.get("/domain")
    async def domain_error() -> None:
        raise DomainConflictError("状态不允许当前操作。")

    @router.get("/provider")
    async def provider_error() -> None:
        raise ProviderUnavailableError("上游暂不可用。")

    @router.get("/unknown")
    async def unknown_error() -> None:
        raise RuntimeError("sensitive-internal-message")

    @router.get("/validation")
    async def validation(value: int) -> dict[str, int]:
        return {"value": value}

    app.include_router(router)
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/test/domain", 409, "DOMAIN_CONFLICT"),
        ("/test/provider", 503, "PROVIDER_UNAVAILABLE"),
        ("/test/validation?value=bad", 422, "VALIDATION_ERROR"),
    ],
)
async def test_problem_details_mapping(test_app, path: str, status: int, code: str) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get(path)
    assert response.status_code == status
    body = response.json()
    assert body["code"] == code
    assert body["detail"]
    assert body["trace_id"] == response.headers["X-Trace-Id"]


@pytest.mark.asyncio
async def test_unknown_error_does_not_leak_internal_message(test_app) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/test/unknown")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "sensitive-internal-message" not in response.text
