from typing import Protocol

from app.providers.commerce.dto import (
    NormalizedProductUrl,
    ProductProviderResult,
    ProductRequest,
    ReviewFetchRequest,
    ReviewProviderResult,
)


class CommerceDataProvider(Protocol):
    async def normalize_url(self, url: str) -> NormalizedProductUrl: ...

    async def fetch_product(self, request: ProductRequest) -> ProductProviderResult: ...

    async def fetch_reviews(self, request: ReviewFetchRequest) -> ReviewProviderResult: ...
