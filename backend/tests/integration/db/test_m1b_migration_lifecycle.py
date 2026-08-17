"""M1-B Alembic 迁移生命周期门禁测试。by AI.Coding"""

from __future__ import annotations

import pytest
from alembic.runtime.migration import MigrationContext
from conftest import migrated_postgres
from sqlalchemy import create_engine

from alembic import command

pytestmark = pytest.mark.integration


def test_m1b_upgrade_current_check_downgrade_and_reupgrade() -> None:
    """验证 0005 可升级、无 drift、可回退并重新升级。by AI.Coding"""
    with migrated_postgres("0001") as database:
        # M1-B 历史门禁固定验证 0005，不随后续纯数据迁移 head 漂移。
        command.upgrade(database.alembic_config, "0005")
        engine = create_engine(database.sync_url)
        try:
            with engine.connect() as connection:
                current = MigrationContext.configure(connection).get_current_revision()
            assert current == "0005"
        finally:
            engine.dispose()
        # 回退 M1-B 再重升，保证部署回滚和再次发布链路均可运行。
        command.downgrade(database.alembic_config, "0004")
        command.upgrade(database.alembic_config, "0005")
        # Alembic check 只能针对当前 head；继续升级纯数据迁移后审核 ORM drift。
        command.upgrade(database.alembic_config, "head")
        command.check(database.alembic_config)
