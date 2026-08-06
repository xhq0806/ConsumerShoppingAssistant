"""M1-B 对比 API 契约和依赖替换测试。by AI.Coding"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_comparison_service
from app.application.comparisons import (
    ComparisonView,
    CreateComparisonCommand,
    ProductView,
)
from app.main import create_app


class _FakeComparisonService:
    """提供无数据库 API 契约测试所需的最小替身。by AI.Coding"""

    def __init__(self) -> None:
        """初始化用于断言路由映射结果的调用记录。by AI.Coding"""
        self.created: tuple[CreateComparisonCommand, str | None] | None = None
        self.comparison_id = uuid4()

    async def create_comparison(
        self, command: CreateComparisonCommand, *, idempotency_key: str | None
    ) -> ComparisonView:
        """记录创建请求并返回稳定空快照摘要。by AI.Coding"""
        # 路由测试不涉及 ORM，返回最小白名单视图以验证 schema 映射。
        self.created = (command, idempotency_key)
        return self._view()

    async def parse_products(self, _comparison_id: object) -> ComparisonView:
        """返回最小详情以覆盖解析路由注册。by AI.Coding"""
        return self._view()

    async def get_comparison(self, _comparison_id: object) -> ComparisonView:
        """返回最小详情以覆盖查询路由注册。by AI.Coding"""
        return self._view()

    async def confirm_products(self, _comparison_id: object, _command: object) -> ComparisonView:
        """返回最小详情以覆盖确认路由注册。by AI.Coding"""
        return self._view()

    def _view(self) -> ComparisonView:
        """构造无敏感字段的稳定应用视图。by AI.Coding"""
        # 固定空事件与快照，专注 API 路由而不复制领域或数据库测试职责。
        return ComparisonView(
            id=self.comparison_id,
            status="draft",
            review_window_days=30,
            progress=0,
            products=(
                ProductView(
                    id=uuid4(),
                    position=0,
                    platform="taobao",
                    external_product_id="10001",
                    parse_status="pending",
                    selected_sku_id=None,
                    latest_snapshot=None,
                    skus=(),
                ),
                ProductView(
                    id=uuid4(),
                    position=1,
                    platform="taobao",
                    external_product_id="10002",
                    parse_status="pending",
                    selected_sku_id=None,
                    latest_snapshot=None,
                    skus=(),
                ),
            ),
            events=(),
        )


@pytest.fixture
def comparison_app() -> tuple[FastAPI, _FakeComparisonService]:
    """创建带 service override 的 FastAPI 应用。by AI.Coding"""
    fake_service = _FakeComparisonService()
    application = create_app()
    # 覆盖统一依赖工厂，证明路由可测试且不会自行访问 ORM 或 Provider。
    application.dependency_overrides[get_comparison_service] = lambda: fake_service
    return application, fake_service


@pytest.mark.asyncio
async def test_create_comparison_contract_and_idempotency_header(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """确认创建端点使用稳定 operation 契约并传递幂等键。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/comparisons",
            headers={"Idempotency-Key": "12345678"},
            json={
                "product_urls": [
                    "https://item.taobao.com/item.htm?id=10001",
                    "https://item.taobao.com/item.htm?id=10002",
                ],
                "review_window_days": 30,
            },
        )
    assert response.status_code == 201
    assert fake_service.created == (
        CreateComparisonCommand(
            (
                "https://item.taobao.com/item.htm?id=10001",
                "https://item.taobao.com/item.htm?id=10002",
            ),
            30,
        ),
        "12345678",
    )
    assert "canonical_url" not in response.text
    assert response.json()["products"][0]["position"] == 0


@pytest.mark.asyncio
async def test_comparison_routes_forbid_extra_input_and_publish_operation_ids(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """确认请求白名单和四个 OpenAPI operation ID 保持稳定。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        invalid = await client.post(
            "/api/v1/comparisons",
            json={
                "product_urls": ["a", "b"],
                "review_window_days": 30,
                "unexpected": True,
            },
        )
        detail = await client.get(f"/api/v1/comparisons/{fake_service.comparison_id}")
        openapi = (await client.get("/openapi.json")).json()
    assert invalid.status_code == 422
    assert detail.status_code == 200
    operation_ids = {
        operation["operationId"]
        for path in openapi["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert {
        "create_comparison",
        "parse_comparison_products",
        "get_comparison",
        "confirm_comparison_products",
    } <= operation_ids
