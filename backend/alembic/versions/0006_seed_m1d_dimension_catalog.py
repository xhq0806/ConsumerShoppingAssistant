"""写入 M1-D 通用与 Fixture 手机品类维度种子。by AI.Coding

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATED_AT = datetime(2026, 8, 11, tzinfo=UTC)
_SEEDS: tuple[dict[str, object], ...] = (
    {
        "id": UUID("00000000-0000-4000-8000-000000000601"),
        "code": "price",
        "name": "价格",
        "category": None,
        "domain": "product_fact",
        "source_type": "product_fact",
        "value_type": "currency",
        "config": {
            "field_paths": ["price"],
            "aliases": ["价格", "预算", "性价比", "价钱"],
            "description": "比较当前商品或已选 SKU 的价格。",
        },
        "default_priority": 0,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "show_unknown",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000602"),
        "code": "brand",
        "name": "品牌",
        "category": None,
        "domain": "product_fact",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["brand"],
            "aliases": ["品牌", "厂商"],
            "description": "展示商品页面明确提供的品牌信息。",
        },
        "default_priority": 20,
        "rankable": False,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "show_unknown",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000603"),
        "code": "shop",
        "name": "店铺",
        "category": None,
        "domain": "product_fact",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["shop_name"],
            "aliases": ["店铺", "商家"],
            "description": "比较商品页面标明的销售店铺。",
        },
        "default_priority": 30,
        "rankable": False,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "show_unknown",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000604"),
        "code": "sku_options",
        "name": "可选规格",
        "category": None,
        "domain": "product_fact",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["skus"],
            "aliases": ["规格", "sku", "颜色", "版本"],
            "description": "展示候选商品可选择的 SKU 和规格组合。",
        },
        "default_priority": 25,
        "rankable": False,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "show_unknown",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000605"),
        "code": "after_sales",
        "name": "售后保障",
        "category": None,
        "domain": "product_fact",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["after_sales"],
            "aliases": ["售后", "退换", "保修", "服务"],
            "description": "比较商品页面提供的退换、保修等售后说明。",
        },
        "default_priority": 35,
        "rankable": False,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "show_unknown",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000606"),
        "code": "brand_founded_year",
        "name": "品牌成立年份",
        "category": None,
        "domain": "brand_background",
        "source_type": "brand_fact",
        "value_type": "integer",
        "config": {
            "field_paths": [],
            "aliases": ["品牌历史", "成立年份"],
            "description": "背景信息，不直接参与推荐；当前阶段尚未采集品牌资料。",
        },
        "default_priority": 90,
        "rankable": False,
        "affects_recommendation": False,
        "min_sample_size": 0,
        "missing_data_policy": "exclude_from_scoring",
        "visualization": "text",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000607"),
        "code": "screen",
        "name": "屏幕",
        "category": "手机",
        "domain": "category_specification",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["specifications.屏幕"],
            "aliases": ["屏幕", "显示", "尺寸", "刷新率"],
            "description": "比较屏幕尺寸及商品页已提供的显示规格。",
        },
        "default_priority": 5,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "show_unknown",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000608"),
        "code": "storage",
        "name": "存储空间",
        "category": "手机",
        "domain": "category_specification",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["selected_sku.attributes.存储", "specifications.存储"],
            "aliases": ["存储", "容量", "内存", "空间"],
            "description": "比较已选 SKU 或商品页面提供的存储容量。",
        },
        "default_priority": 10,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "show_unknown",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000609"),
        "code": "battery_life",
        "name": "续航",
        "category": "手机",
        "domain": "category_specification",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["specifications.电池", "specifications.续航"],
            "aliases": ["续航", "电池", "待机"],
            "description": "比较商品页面提供的电池与续航规格。",
        },
        "default_priority": 15,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "lower_confidence",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000610"),
        "code": "camera",
        "name": "拍照能力",
        "category": "手机",
        "domain": "category_specification",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["specifications.相机", "specifications.摄像头"],
            "aliases": ["拍照", "相机", "摄像头", "影像"],
            "description": "比较商品页面明确提供的相机和影像规格。",
        },
        "default_priority": 16,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "lower_confidence",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000611"),
        "code": "performance",
        "name": "性能",
        "category": "手机",
        "domain": "category_specification",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["specifications.处理器", "specifications.芯片"],
            "aliases": ["性能", "处理器", "芯片", "游戏"],
            "description": "比较商品页面提供的处理器和性能相关规格。",
        },
        "default_priority": 17,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "lower_confidence",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000612"),
        "code": "weight",
        "name": "重量与便携性",
        "category": "手机",
        "domain": "category_specification",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["specifications.重量"],
            "aliases": ["重量", "便携", "轻薄", "机身过重"],
            "description": "比较商品页面提供的重量和便携性信息。",
        },
        "default_priority": 18,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "lower_confidence",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000613"),
        "code": "charging",
        "name": "充电",
        "category": "手机",
        "domain": "category_specification",
        "source_type": "product_fact",
        "value_type": "text",
        "config": {
            "field_paths": ["specifications.充电", "specifications.快充"],
            "aliases": ["充电", "快充", "充电速度"],
            "description": "比较商品页面明确提供的充电规格。",
        },
        "default_priority": 19,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 0,
        "missing_data_policy": "lower_confidence",
        "visualization": "table",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000614"),
        "code": "heating",
        "name": "发热体验",
        "category": "手机",
        "domain": "review_experience",
        "source_type": "review_metric",
        "value_type": "percentage",
        "config": {
            "field_paths": [],
            "aliases": ["发热", "温度", "烫"],
            "description": "后续根据近期评论统计发热反馈；当前阶段尚无评论指标。",
        },
        "default_priority": 21,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 10,
        "missing_data_policy": "lower_confidence",
        "visualization": "bar",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000615"),
        "code": "signal_quality",
        "name": "信号体验",
        "category": "手机",
        "domain": "review_experience",
        "source_type": "review_metric",
        "value_type": "percentage",
        "config": {
            "field_paths": [],
            "aliases": ["信号", "网络", "通话"],
            "description": "后续根据近期评论统计信号反馈；当前阶段尚无评论指标。",
        },
        "default_priority": 22,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 10,
        "missing_data_policy": "lower_confidence",
        "visualization": "bar",
        "user_removable": True,
        "enabled": True,
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000616"),
        "code": "review_reputation",
        "name": "近期评论口碑",
        "category": "手机",
        "domain": "review_experience",
        "source_type": "review_metric",
        "value_type": "rating",
        "config": {
            "field_paths": [],
            "aliases": ["评论", "口碑", "评价", "真实体验"],
            "description": "后续汇总指定评论窗口的体验指标；当前阶段尚未执行评论分析。",
        },
        "default_priority": 23,
        "rankable": True,
        "affects_recommendation": True,
        "min_sample_size": 10,
        "missing_data_policy": "lower_confidence",
        "visualization": "bar",
        "user_removable": True,
        "enabled": True,
    },
)


def upgrade() -> None:
    """幂等写入 M1-D 受控目录种子且不修改现有表结构。by AI.Coding"""
    dimensions = _dimension_table()
    rows = [
        {
            **seed,
            "created_at": _CREATED_AT,
            "updated_at": _CREATED_AT,
        }
        for seed in _SEEDS
    ]
    statement = postgresql.insert(dimensions).values(rows)
    op.get_bind().execute(statement.on_conflict_do_nothing(index_elements=["code"]))


def downgrade() -> None:
    """仅删除本迁移声明的固定维度 code。by AI.Coding"""
    dimensions = _dimension_table()
    task_dimensions = sa.table(
        "task_dimensions",
        sa.column("dimension_id", sa.UUID()),
    )
    seed_ids = [seed["id"] for seed in _SEEDS]
    op.get_bind().execute(
        sa.delete(task_dimensions).where(task_dimensions.c.dimension_id.in_(seed_ids))
    )
    op.get_bind().execute(
        sa.delete(dimensions).where(dimensions.c.code.in_([seed["code"] for seed in _SEEDS]))
    )


def _dimension_table() -> sa.TableClause:
    """声明数据迁移所需的最小维度表结构。by AI.Coding"""
    return sa.table(
        "dimension_definitions",
        sa.column("id", sa.UUID()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("domain", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("value_type", sa.String()),
        sa.column("config", postgresql.JSONB()),
        sa.column("default_priority", sa.Integer()),
        sa.column("rankable", sa.Boolean()),
        sa.column("affects_recommendation", sa.Boolean()),
        sa.column("min_sample_size", sa.Integer()),
        sa.column("missing_data_policy", sa.String()),
        sa.column("visualization", sa.String()),
        sa.column("user_removable", sa.Boolean()),
        sa.column("enabled", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
