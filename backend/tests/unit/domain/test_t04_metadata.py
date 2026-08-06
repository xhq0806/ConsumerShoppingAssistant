"""T04 ORM metadata 与枚举存储测试。by AI.Coding"""

from sqlalchemy import Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.sqltypes import Enum as SqlEnum

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import BrandProfile, DimensionDefinition


def test_metadata_registers_t03_and_t04_tables() -> None:
    """公共 metadata 应注册 T03 五表和 T04 四表。by AI.Coding"""
    assert {
        "comparison_tasks",
        "comparison_products",
        "product_snapshots",
        "product_skus",
        "task_events",
        "brand_profiles",
        "brand_sources",
        "dimension_definitions",
        "task_dimensions",
    }.issubset(Base.metadata.tables)


def test_brand_profile_factory_normalizes_name() -> None:
    """品牌构造器应生成确定性标准名。by AI.Coding"""
    brand = BrandProfile.create(display_name=" ACME（中国） ")
    assert brand.display_name == "ACME（中国）"
    assert brand.normalized_name == "acme 中国"


def test_dimension_definition_exposes_config_and_explicit_semantics() -> None:
    """维度定义明确保存配置、可排名和推荐影响语义。by AI.Coding"""
    assert isinstance(DimensionDefinition.__table__.c.config.type, JSONB)
    assert {"rankable", "affects_recommendation"} <= set(
        DimensionDefinition.__table__.columns.keys()
    )
    assert "comparable" not in DimensionDefinition.__table__.columns
    assert "participates_in_recommendation" not in DimensionDefinition.__table__.columns


def test_all_t04_enum_columns_use_varchar_without_native_enum() -> None:
    """T04 枚举列必须落为 VARCHAR 且由显式 CHECK 约束。by AI.Coding"""
    enum_columns = [
        BrandProfile.__table__.c.verification_status,
        DimensionDefinition.__table__.c.domain,
        DimensionDefinition.__table__.c.source_type,
        DimensionDefinition.__table__.c.value_type,
        DimensionDefinition.__table__.c.missing_data_policy,
        DimensionDefinition.__table__.c.visualization,
    ]
    enum_types = [column.type for column in enum_columns]
    assert all(isinstance(enum_type, Enum) for enum_type in enum_types)
    assert all(
        enum_type.native_enum is False for enum_type in enum_types if isinstance(enum_type, SqlEnum)
    )
    assert all(
        enum_type.create_constraint is False
        for enum_type in enum_types
        if isinstance(enum_type, SqlEnum)
    )
