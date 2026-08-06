"""增加 M1-B 创建幂等持久化约束。by AI.Coding

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为任务增加不可逆幂等摘要、请求指纹及数据库门禁。by AI.Coding"""
    # 两列保持可空以兼容 M1-A 历史任务，CHECK 禁止任一列单独存在。
    op.add_column(
        "comparison_tasks", sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "comparison_tasks",
        sa.Column("create_request_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_comparison_tasks_idempotency_fields_paired"),
        "comparison_tasks",
        "(idempotency_key_hash IS NULL) = (create_request_fingerprint IS NULL)",
    )
    # PostgreSQL 部分唯一索引仅约束携带幂等键的新任务，允许历史 NULL 行并存。
    op.create_index(
        "uq_comparison_tasks_idempotency_key_hash_not_null",
        "comparison_tasks",
        ["idempotency_key_hash"],
        unique=True,
        postgresql_where=sa.text("idempotency_key_hash IS NOT NULL"),
    )


def downgrade() -> None:
    """按依赖反向删除 M1-B 幂等字段及其约束。by AI.Coding"""
    # 先移除依赖列的索引和 CHECK，再删除可空字段以保证迁移可逆。
    op.drop_index("uq_comparison_tasks_idempotency_key_hash_not_null", "comparison_tasks")
    op.drop_constraint(
        op.f("ck_comparison_tasks_idempotency_fields_paired"),
        "comparison_tasks",
        type_="check",
    )
    op.drop_column("comparison_tasks", "create_request_fingerprint")
    op.drop_column("comparison_tasks", "idempotency_key_hash")
