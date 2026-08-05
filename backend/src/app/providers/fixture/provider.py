import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import (
    ProviderInvalidResponseError,
    ProviderNotFoundError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.providers.commerce.dto import (
    NormalizedProductUrl,
    ProductProviderResult,
    ProductRequest,
    ProviderFixtureEnvelope,
    ReviewFetchRequest,
    ReviewProviderResult,
)
from app.providers.commerce.url_normalizer import TaobaoUrlNormalizer


class FixtureCommerceDataProvider:
    def __init__(self, settings: Settings, data_dir: Path | None = None) -> None:
        self._normalizer = TaobaoUrlNormalizer(settings, resolver=lambda _host: ["8.8.8.8"])
        self._data_dir = data_dir or Path(__file__).with_name("data")

    async def normalize_url(self, url: str) -> NormalizedProductUrl:
        return self._normalizer.normalize(url)

    async def fetch_product(self, request: ProductRequest) -> ProductProviderResult:
        envelope = self._load(f"product-{request.product_url.external_product_id}.json")
        self._raise_fixture_error(envelope)
        try:
            return ProductProviderResult.model_validate(envelope.payload)
        except ValidationError as exc:
            raise ProviderInvalidResponseError("Fixture 商品数据不符合 Provider 契约。") from exc

    async def fetch_reviews(self, request: ReviewFetchRequest) -> ReviewProviderResult:
        filename = f"reviews-{request.product_url.external_product_id}-{request.window_days}.json"
        envelope = self._load(filename)
        self._raise_fixture_error(envelope)
        try:
            result = ReviewProviderResult.model_validate(envelope.payload)
        except ValidationError as exc:
            raise ProviderInvalidResponseError("Fixture 评论数据不符合 Provider 契约。") from exc
        if len(result.reviews) <= request.max_reviews:
            return result
        reviews = result.reviews[: request.max_reviews]
        return result.model_copy(update={"reviews": reviews, "fetched_count": len(reviews)})

    def _load(self, filename: str) -> ProviderFixtureEnvelope:
        path = self._data_dir / filename
        if path.parent != self._data_dir or not path.is_file():
            raise ProviderNotFoundError("Fixture 中没有对应的合成商品或评论数据。")
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
            return ProviderFixtureEnvelope.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ProviderInvalidResponseError("Fixture 文件无法解析。") from exc

    @staticmethod
    def _raise_fixture_error(envelope: ProviderFixtureEnvelope) -> None:
        if envelope.kind == "success":
            return
        if envelope.error_code == "rate_limited":
            raise ProviderRateLimitedError("Fixture 模拟了数据服务限流。")
        if envelope.error_code == "timeout":
            raise ProviderUnavailableError("Fixture 模拟了数据服务超时。")
        if envelope.error_code == "not_found":
            raise ProviderNotFoundError("Fixture 模拟了商品不存在。")
        raise ProviderInvalidResponseError("Fixture 模拟了未知 Provider 错误。")
