"""M1-B Alembic 迁移生命周期门禁测试。by AI.Coding"""

from __future__ import annotations

from alembic.runtime.migration import MigrationContext
from conftest import migrated_postgres
from sqlalchemy import create_engine

from alembic import command


def test_m1b_upgrade_current_check_downgrade_and_reupgrade() -> None:
    """验证 0005 可升级、无 drift、可回退并重新升级。by AI.Coding"""
    with migrated_postgres("0001") as database:
        # 从 M1-A 空基线完整走到 head，并用 Alembic check 审核 ORM metadata。
        command.upgrade(database.alembic_config, "head")
        command.check(database.alembic_config)
        engine = create_engine(database.sync_url)
        try:
            with engine.connect() as connection:
                current = MigrationContext.configure(connection).get_current_revision()
            assert current == "0005"
        finally:
            engine.dispose()
        # 回退 M1-B 再重升，保证部署回滚和再次发布链路均可运行。
        command.downgrade(database.alembic_config, "0004")
        command.upgrade(database.alembic_config, "head")
        command.check(database.alembic_config)
