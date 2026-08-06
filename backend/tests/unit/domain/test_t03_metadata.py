"""T03 ORM metadata 与 DTO 入库 seam 测试。by AI.Coding"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.core.errors import DomainConflictError
from app.infrastructure.db.base import Base
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.models import ComparisonProduct, ProductSku, ProductSnapshot
from app.providers.commerce.dto import NormalizedProductUrl, ProductDTO, SkuDTO, SourceReference


def _repository() -> ComparisonRepository:
    """创建只验证同步 add seam 的仓储测试替身。by AI.Coding"""
    return ComparisonRepository(Mock())


def test_metadata_registers_all_t03_tables() -> None:
    """公共 metadata 应继续完整注册 T03 五表。by AI.Coding"""
    assert {
        "comparison_tasks",
        "comparison_products",
        "product_snapshots",
        "product_skus",
        "task_events",
    }.issubset(Base.metadata.tables)


def test_candidate_persists_only_normalized_url_fields() -> None:
    """候选商品只能经 Repository 的规范化 URL DTO seam 创建。by AI.Coding"""
    product_url = NormalizedProductUrl(
        canonical_url="https://item.taobao.com/item.htm?id=123",
        host="item.taobao.com",
        external_product_id="123",
        safe_url_fingerprint="a" * 64,
    )
    candidate = _repository().add_candidate_from_dto(
        comparison_id=uuid.uuid4(), position=0, product_url=product_url
    )
    assert candidate.canonical_url == str(product_url.canonical_url)
    assert candidate.external_product_id == "123"
    assert candidate.safe_url_fingerprint == "a" * 64
    assert "raw_url" not in candidate.__table__.columns


def test_product_and_sku_dto_mapping_preserves_decimal_and_source() -> None:
    """Repository DTO seam 保留精确价格和最小来源字段。by AI.Coding"""
    product_id = uuid.uuid4()
    source = SourceReference(
        provider="fixture", source_id="product-123", obtained_at=datetime.now(UTC)
    )
    product = ProductDTO(
        external_product_id="123",
        title="测试商品",
        price=Decimal("199.90"),
        source=source,
    )
    sku = SkuDTO(external_sku_id="sku-1", name="黑色", price=Decimal("209.90"))
    repository = _repository()
    snapshot = repository.add_snapshot_from_dto(comparison_product_id=product_id, product=product)
    sku_model = repository.add_sku_from_dto(comparison_product_id=product_id, sku=sku)
    assert snapshot.price == Decimal("199.90")
    assert snapshot.source == {
        "provider": "fixture",
        "source_id": "product-123",
        "obtained_at": source.obtained_at.isoformat(),
    }
    assert sku_model.price == Decimal("209.90")


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (
            ComparisonProduct,
            {
                "comparison_id": uuid.uuid4(),
                "position": 0,
                "canonical_url": "https://item.taobao.com/item.htm?id=1",
                "platform": "taobao",
                "external_product_id": "1",
                "safe_url_fingerprint": "a" * 64,
            },
        ),
        (ProductSnapshot, {"comparison_product_id": uuid.uuid4(), "title": "x"}),
        (ProductSku, {"comparison_product_id": uuid.uuid4(), "external_sku_id": "x"}),
    ],
)
def test_dto_protected_models_reject_direct_application_construction(
    model: type[object], values: dict[str, object]
) -> None:
    """普通 Python 应用代码不能直接传持久化白名单字段绕过 DTO seam。by AI.Coding"""
    with pytest.raises(DomainConflictError, match="Repository DTO"):
        model(**values)  # type: ignore[call-arg]
