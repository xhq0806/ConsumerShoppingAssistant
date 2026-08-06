"""创建 T04 品牌与维度目录数据模型。by AI.Coding

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建且仅创建 T04 的四张目录相关表。by AI.Coding"""
    # 品牌主档先于字段级来源创建，删除品牌时来源随主档级联清理。
    op.create_table(
        "brand_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), nullable=False),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("parent_company", sa.String(length=255), nullable=True),
        sa.Column("country_or_region", sa.String(length=255), nullable=True),
        sa.Column("primary_categories", postgresql.JSONB(), nullable=False),
        sa.Column("verification_status", sa.String(length=10), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'rejected')",
            name=op.f("ck_brand_profiles_verification_status"),
        ),
        sa.CheckConstraint(
            "founded_year IS NULL OR founded_year BETWEEN 1 AND 9999",
            name=op.f("ck_brand_profiles_founded_year"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_profiles")),
        sa.UniqueConstraint("normalized_name", name=op.f("uq_brand_profiles_normalized_name")),
    )
    op.create_table(
        "brand_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("field_name", sa.String(length=19), nullable=False),
        sa.Column("source_type", sa.String(length=22), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_identifier", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("obtained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "field_name IN ('founded_year', 'parent_company', 'country_or_region', "
            "'primary_categories')",
            name=op.f("ck_brand_sources_field_name"),
        ),
        sa.CheckConstraint(
            "source_type IN ('official_website', 'trusted_knowledge_base', 'manual')",
            name=op.f("ck_brand_sources_source_type"),
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_brand_sources_confidence")),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brand_profiles.id"],
            name=op.f("fk_brand_sources_brand_id_brand_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_sources")),
    )
    op.create_index(op.f("ix_brand_sources_brand_id"), "brand_sources", ["brand_id"])

    # 维度全部用 VARCHAR 与显式 CHECK，避免 PostgreSQL native enum 生命周期耦合。
    op.create_table(
        "dimension_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=22), nullable=False),
        sa.Column("source_type", sa.String(length=15), nullable=False),
        sa.Column("value_type", sa.String(length=10), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("default_priority", sa.Integer(), nullable=False),
        sa.Column("rankable", sa.Boolean(), nullable=False),
        sa.Column("affects_recommendation", sa.Boolean(), nullable=False),
        sa.Column("min_sample_size", sa.Integer(), nullable=False),
        sa.Column("missing_data_policy", sa.String(length=20), nullable=False),
        sa.Column("visualization", sa.String(length=12), nullable=False),
        sa.Column("user_removable", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "domain IN ('product_fact', 'brand_background', 'category_specification', "
            "'review_experience', 'user_preference')",
            name=op.f("ck_dimension_definitions_domain"),
        ),
        sa.CheckConstraint(
            "source_type IN ('product_fact', 'brand_fact', 'review_metric', "
            "'derived_metric', 'user_preference')",
            name=op.f("ck_dimension_definitions_source_type"),
        ),
        sa.CheckConstraint(
            "value_type IN ('text', 'integer', 'decimal', 'boolean', 'percentage', "
            "'currency', 'rating')",
            name=op.f("ck_dimension_definitions_value_type"),
        ),
        sa.CheckConstraint(
            "visualization IN ('text', 'table', 'bar', 'radar', 'trend', 'distribution')",
            name=op.f("ck_dimension_definitions_visualization"),
        ),
        sa.CheckConstraint(
            "missing_data_policy IN ('show_unknown', 'exclude_from_scoring', 'lower_confidence')",
            name=op.f("ck_dimension_definitions_missing_data_policy"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(config) = 'object'", name=op.f("ck_dimension_definitions_config_object")
        ),
        sa.CheckConstraint(
            "default_priority >= 0", name=op.f("ck_dimension_definitions_default_priority")
        ),
        sa.CheckConstraint(
            "min_sample_size >= 0", name=op.f("ck_dimension_definitions_min_sample_size")
        ),
        sa.CheckConstraint(
            "NOT (code = 'brand_founded_year' AND affects_recommendation)",
            name=op.f("ck_dimension_definitions_founded_year_not_scored"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dimension_definitions")),
        sa.UniqueConstraint("code", name=op.f("uq_dimension_definitions_code")),
    )
    op.create_index(
        "ix_dimension_definitions_category_enabled",
        "dimension_definitions",
        ["category", "enabled"],
    )

    op.create_table(
        "task_dimensions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("dimension_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("user_selected", sa.Boolean(), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(selected AND position IS NOT NULL AND position >= 0) OR "
            "(NOT selected AND position IS NULL)",
            name=op.f("ck_task_dimensions_selected_position"),
        ),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["comparison_tasks.id"],
            name=op.f("fk_task_dimensions_comparison_id_comparison_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dimension_id"],
            ["dimension_definitions.id"],
            name=op.f("fk_task_dimensions_dimension_id_dimension_definitions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_dimensions")),
        sa.UniqueConstraint(
            "comparison_id", "dimension_id", name="uq_task_dimensions_comparison_dimension"
        ),
    )
    op.create_index(op.f("ix_task_dimensions_comparison_id"), "task_dimensions", ["comparison_id"])
    op.create_index(op.f("ix_task_dimensions_dimension_id"), "task_dimensions", ["dimension_id"])
    op.create_index(
        "uq_task_dimensions_selected_position",
        "task_dimensions",
        ["comparison_id", "position"],
        unique=True,
        postgresql_where=sa.text("selected AND position IS NOT NULL"),
    )


def downgrade() -> None:
    """按引用依赖反向移除且仅移除 T04 四张表。by AI.Coding"""
    # 先移除任务引用表，再移除两个共享目录及品牌字段来源。
    op.drop_table("task_dimensions")
    op.drop_table("dimension_definitions")
    op.drop_table("brand_sources")
    op.drop_table("brand_profiles")
