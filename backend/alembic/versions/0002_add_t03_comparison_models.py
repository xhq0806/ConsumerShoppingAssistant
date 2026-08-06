"""创建 T03 对比任务与商品数据模型。by AI.Coding

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMPARISON_STATUSES = (
    "draft",
    "parsing",
    "awaiting_product_confirmation",
    "awaiting_dimension_confirmation",
    "ready_for_analysis",
    "queued",
    "fetching",
    "processing",
    "completed",
    "partially_completed",
    "failed",
    "deleted",
)
PRODUCT_PARSE_STATUSES = ("pending", "parsing", "parsed", "needs_confirmation", "failed")
TASK_STAGES = (
    "created",
    "product_parsing",
    "product_confirmation",
    "dimension_confirmation",
    "queued",
    "data_fetching",
    "analysis",
    "reporting",
    "finished",
)
TASK_EVENT_TYPES = ("status_changed", "progress_updated", "warning", "error", "info")


def _sql_values(values: tuple[str, ...]) -> str:
    """生成只用于固定领域常量的 CHECK 值列表。by AI.Coding"""
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """创建且仅创建 T03 的五张业务表。by AI.Coding"""
    # 先创建聚合根，再按外键依赖创建私有子图。
    op.create_table(
        "comparison_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=31), nullable=False),
        sa.Column("review_window_days", sa.Integer(), nullable=False),
        sa.Column("preferences", postgresql.JSONB(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("partial_result", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({_sql_values(COMPARISON_STATUSES)})",
            name=op.f("ck_comparison_tasks_status"),
        ),
        sa.CheckConstraint(
            "review_window_days IN (30, 60)",
            name=op.f("ck_comparison_tasks_review_window_days"),
        ),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name=op.f("ck_comparison_tasks_progress")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comparison_tasks")),
    )
    op.create_index(
        "ix_comparison_tasks_status_created_at",
        "comparison_tasks",
        ["status", "created_at"],
    )

    op.create_table(
        "comparison_products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("platform", sa.String(length=6), nullable=False),
        sa.Column("external_product_id", sa.String(length=255), nullable=False),
        sa.Column("safe_url_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("selected_sku_id", sa.UUID(), nullable=True),
        sa.Column("parse_status", sa.String(length=18), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("platform IN ('taobao')", name=op.f("ck_comparison_products_platform")),
        sa.CheckConstraint(
            f"parse_status IN ({_sql_values(PRODUCT_PARSE_STATUSES)})",
            name=op.f("ck_comparison_products_parse_status"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_comparison_products_position")),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["comparison_tasks.id"],
            name=op.f("fk_comparison_products_comparison_id_comparison_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comparison_products")),
        sa.UniqueConstraint(
            "comparison_id",
            "position",
            name="uq_comparison_products_comparison_id_position",
        ),
        sa.UniqueConstraint(
            "comparison_id",
            "platform",
            "external_product_id",
            name="uq_comparison_products_task_platform_external_id",
        ),
        sa.UniqueConstraint(
            "comparison_id",
            "safe_url_fingerprint",
            name="uq_comparison_products_task_fingerprint",
        ),
    )
    op.create_index(
        op.f("ix_comparison_products_comparison_id"),
        "comparison_products",
        ["comparison_id"],
    )
    op.create_index(
        "ix_comparison_products_safe_url_fingerprint",
        "comparison_products",
        ["safe_url_fingerprint"],
    )

    op.create_table(
        "product_skus",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_product_id", sa.UUID(), nullable=False),
        sa.Column("external_sku_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("selectable", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["comparison_product_id"],
            ["comparison_products.id"],
            name=op.f("fk_product_skus_comparison_product_id_comparison_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_skus")),
        sa.UniqueConstraint(
            "comparison_product_id",
            "external_sku_id",
            name=op.f("uq_product_skus_comparison_product_id"),
        ),
        sa.UniqueConstraint("comparison_product_id", "id", name="uq_product_skus_product_id_id"),
    )
    op.create_index(
        op.f("ix_product_skus_comparison_product_id"),
        "product_skus",
        ["comparison_product_id"],
    )
    # 单列外键负责删除已选 SKU 时清空选择，复合外键只负责归属一致性。
    op.create_foreign_key(
        "fk_comparison_products_selected_sku_id_product_skus",
        "comparison_products",
        "product_skus",
        ["selected_sku_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_comparison_products_selected_sku_belongs_to_product",
        "comparison_products",
        "product_skus",
        ["id", "selected_sku_id"],
        ["comparison_product_id", "id"],
    )

    op.create_table(
        "product_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_product_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("shop_name", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("specifications", postgresql.JSONB(), nullable=False),
        sa.Column("after_sales", postgresql.JSONB(), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["comparison_product_id"],
            ["comparison_products.id"],
            name=op.f("fk_product_snapshots_comparison_product_id_comparison_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_snapshots")),
    )
    op.create_index(
        op.f("ix_product_snapshots_comparison_product_id"),
        "product_snapshots",
        ["comparison_product_id"],
    )
    op.create_index(op.f("ix_product_snapshots_captured_at"), "product_snapshots", ["captured_at"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.String(length=22), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"stage IN ({_sql_values(TASK_STAGES)})",
            name=op.f("ck_task_events_stage"),
        ),
        sa.CheckConstraint(
            f"event_type IN ({_sql_values(TASK_EVENT_TYPES)})",
            name=op.f("ck_task_events_event_type"),
        ),
        sa.CheckConstraint(
            "progress IS NULL OR progress BETWEEN 0 AND 100",
            name=op.f("ck_task_events_progress"),
        ),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["comparison_tasks.id"],
            name=op.f("fk_task_events_comparison_id_comparison_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_events")),
    )
    op.create_index(
        "ix_task_events_comparison_id_created_at",
        "task_events",
        ["comparison_id", "created_at"],
    )


def downgrade() -> None:
    """按依赖反向移除且仅移除 T03 五张表。by AI.Coding"""
    # 先移除循环依赖外键，再删除私有子表与聚合根。
    op.drop_constraint(
        "fk_comparison_products_selected_sku_belongs_to_product",
        "comparison_products",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_comparison_products_selected_sku_id_product_skus",
        "comparison_products",
        type_="foreignkey",
    )
    op.drop_table("task_events")
    op.drop_table("product_snapshots")
    op.drop_table("product_skus")
    op.drop_table("comparison_products")
    op.drop_table("comparison_tasks")
