"""M1-B 对比 API 契约和依赖替换测试。by AI.Coding"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_comparison_service
from app.application.comparisons import (
    ComparisonView,
    ConfirmDimensionsCommand,
    CreateComparisonCommand,
    DimensionSetView,
    DimensionView,
    ProductView,
    UpdatePreferencesCommand,
)
from app.domain.comparisons.preferences import UserPreferences
from app.main import create_app


class _FakeComparisonService:
    """提供无数据库 API 契约测试所需的最小替身。by AI.Coding"""

    def __init__(self) -> None:
        """初始化用于断言路由映射结果的调用记录。by AI.Coding"""
        self.created: tuple[CreateComparisonCommand, str | None] | None = None
        self.updated_preferences: UpdatePreferencesCommand | None = None
        self.confirmed_dimensions: ConfirmDimensionsCommand | None = None
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

    async def update_preferences(
        self, _comparison_id: object, command: UpdatePreferencesCommand
    ) -> ComparisonView:
        """记录偏好替换命令并返回带规范化偏好的详情。by AI.Coding"""
        self.updated_preferences = command
        return self._view(
            preferences=UserPreferences.create(
                budget_min=command.budget_min,
                budget_max=command.budget_max,
                usage_scenarios=command.usage_scenarios,
                priority_concerns=command.priority_concerns,
                deal_breakers=command.deal_breakers,
            )
        )

    async def generate_dimension_recommendations(self, _comparison_id: object) -> DimensionSetView:
        """返回稳定的维度候选集合。by AI.Coding"""
        return self._dimension_set()

    async def get_dimensions(self, _comparison_id: object) -> DimensionSetView:
        """返回稳定的维度恢复集合。by AI.Coding"""
        return self._dimension_set()

    async def confirm_dimensions(
        self, _comparison_id: object, command: ConfirmDimensionsCommand
    ) -> DimensionSetView:
        """记录确认命令并返回 queued 集合。by AI.Coding"""
        self.confirmed_dimensions = command
        return self._dimension_set(status="queued")

    def _view(self, *, preferences: UserPreferences | None = None) -> ComparisonView:
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
            preferences=preferences,
        )

    def _dimension_set(
        self, *, status: str = "awaiting_dimension_confirmation"
    ) -> DimensionSetView:
        """构造不暴露 config 的最小动态维度视图。by AI.Coding"""
        return DimensionSetView(
            comparison_id=self.comparison_id,
            status=status,
            category="手机",
            generated=True,
            dimensions=(
                DimensionView(
                    code="price",
                    name="价格",
                    source_type="product_fact",
                    selected=True,
                    position=0,
                    user_selected=False,
                    reason="候选商品在该维度存在差异",
                    data_risk="available",
                    has_difference=True,
                    affects_recommendation=True,
                    user_removable=True,
                    description="比较价格。",
                ),
            ),
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
        "update_comparison_preferences",
        "generate_comparison_dimension_recommendations",
        "get_comparison_dimensions",
        "confirm_comparison_dimensions",
    } <= operation_ids


@pytest.mark.asyncio
async def test_update_preferences_contract_maps_decimal_and_text_collections(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """偏好接口应映射金额、文本集合并返回稳定恢复结构。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.put(
            f"/api/v1/comparisons/{fake_service.comparison_id}/preferences",
            json={
                "review_window_days": 60,
                "budget_min": "3000.00",
                "budget_max": "4500.00",
                "usage_scenarios": ["日常通勤", "旅行拍照"],
                "priority_concerns": ["续航", "拍照"],
                "deal_breakers": ["机身过重"],
            },
        )

    assert response.status_code == 200
    assert fake_service.updated_preferences == UpdatePreferencesCommand(
        review_window_days=60,
        budget_min=Decimal("3000.00"),
        budget_max=Decimal("4500.00"),
        usage_scenarios=("日常通勤", "旅行拍照"),
        priority_concerns=("续航", "拍照"),
        deal_breakers=("机身过重",),
    )
    assert response.json()["preferences"] == {
        "budget_min": "3000.00",
        "budget_max": "4500.00",
        "usage_scenarios": ["日常通勤", "旅行拍照"],
        "priority_concerns": ["续航", "拍照"],
        "deal_breakers": ["机身过重"],
    }


@pytest.mark.asyncio
async def test_update_preferences_normalizes_before_text_and_count_limits(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """HTTP 层不得在领域规范化前误拒绝可折叠空白和重复文本。by AI.Coding"""
    application, fake_service = comparison_app
    raw_scenario = f"通勤{' ' * 100}拍照"
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.put(
            f"/api/v1/comparisons/{fake_service.comparison_id}/preferences",
            json={
                "review_window_days": 30,
                "budget_min": None,
                "budget_max": "4500.00",
                "usage_scenarios": [raw_scenario] * 6,
                "priority_concerns": ["续航"],
                "deal_breakers": [],
            },
        )

    assert response.status_code == 200
    assert response.json()["preferences"]["usage_scenarios"] == ["通勤 拍照"]


@pytest.mark.asyncio
async def test_dimension_routes_generate_query_and_confirm_ordered_codes(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """三个维度端点映射白名单响应并保持用户确认顺序。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        generated = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/recommendations"
        )
        queried = await client.get(f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions")
        confirmed = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/confirm",
            json={"dimension_codes": ["price", "storage"]},
        )

    assert generated.status_code == 200
    assert queried.json()["dimensions"][0]["data_risk"] == "available"
    assert "config" not in queried.text
    assert confirmed.json()["status"] == "queued"
    assert fake_service.confirmed_dimensions == ConfirmDimensionsCommand(("price", "storage"))


@pytest.mark.asyncio
async def test_dimension_confirmation_rejects_empty_and_extra_fields(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """HTTP Schema 在进入应用服务前拒绝空维度和额外字段。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        empty = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/confirm",
            json={"dimension_codes": []},
        )
        extra = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/confirm",
            json={"dimension_codes": ["price"], "unexpected": True},
        )

    assert empty.status_code == 422
    assert extra.status_code == 422
