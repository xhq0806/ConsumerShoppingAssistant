import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ProviderRateLimitedError
from app.providers.commerce.dto import ProductRequest, ReviewFetchRequest
from app.providers.fixture.provider import FixtureCommerceDataProvider


@pytest.fixture
def provider() -> FixtureCommerceDataProvider:
    return FixtureCommerceDataProvider(Settings())


@pytest.mark.asyncio
async def test_fixture_provider_reads_product_and_skus(
    provider: FixtureCommerceDataProvider,
) -> None:
    url = await provider.normalize_url("https://item.taobao.com/item.htm?id=10001")
    result = await provider.fetch_product(ProductRequest(product_url=url))
    assert result.product.title == "星河 X1 合成测试手机"
    assert len(result.skus) == 2


@pytest.mark.asyncio
async def test_fixture_provider_returns_prompt_injection_as_plain_review_text(
    provider: FixtureCommerceDataProvider,
) -> None:
    url = await provider.normalize_url("https://item.taobao.com/item.htm?id=10001")
    result = await provider.fetch_reviews(ReviewFetchRequest(product_url=url, window_days=30))
    assert result.fetched_count == 3
    assert any("忽略此前规则" in review.content for review in result.reviews)


@pytest.mark.asyncio
async def test_fixture_provider_expresses_empty_reviews_as_success(
    provider: FixtureCommerceDataProvider,
) -> None:
    url = await provider.normalize_url("https://item.taobao.com/item.htm?id=10002")
    result = await provider.fetch_reviews(ReviewFetchRequest(product_url=url, window_days=30))
    assert result.fetched_count == 0
    assert result.reviews == []


@pytest.mark.asyncio
async def test_fixture_provider_maps_rate_limit_error(
    provider: FixtureCommerceDataProvider,
) -> None:
    url = await provider.normalize_url("https://item.taobao.com/item.htm?id=429")
    with pytest.raises(ProviderRateLimitedError):
        await provider.fetch_product(ProductRequest(product_url=url))


@pytest.mark.asyncio
async def test_review_request_hard_limits_single_product_to_500(
    provider: FixtureCommerceDataProvider,
) -> None:
    """评论请求在 DTO 边界拒绝超过 500 条的单商品样本。by AI.Coding"""
    url = await provider.normalize_url("https://item.taobao.com/item.htm?id=10001")
    with pytest.raises(ValidationError):
        ReviewFetchRequest(product_url=url, window_days=30, max_reviews=501)
