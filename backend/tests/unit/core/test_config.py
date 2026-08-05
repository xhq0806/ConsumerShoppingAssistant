from app.core.config import Settings


def test_parses_comma_separated_taobao_allowed_hosts(monkeypatch) -> None:
    """验证容器常用的逗号分隔环境变量可由 Settings 正常加载。"""
    monkeypatch.setenv(
        "TAOBAO_ALLOWED_HOSTS",
        "item.taobao.com, detail.tmall.com",
    )

    settings = Settings(_env_file=None)

    assert settings.taobao_allowed_hosts == (
        "item.taobao.com",
        "detail.tmall.com",
    )
