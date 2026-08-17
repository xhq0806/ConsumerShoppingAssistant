import pytest
from pydantic import ValidationError

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


def test_fake_llm_does_not_require_deepseek_api_key() -> None:
    """默认 fake provider 不要求任何真实模型凭据。by AI.Coding"""
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "fake"
    assert settings.deepseek_api_key is None


def test_deepseek_provider_requires_non_empty_secret_key() -> None:
    """启用 DeepSeek 时空 API Key 在配置加载阶段失败。by AI.Coding"""
    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY"):
        Settings(
            _env_file=None,
            llm_provider="deepseek",
            deepseek_api_key="",
        )


def test_deepseek_configuration_keeps_api_key_secret() -> None:
    """DeepSeek API Key 使用 SecretStr，模型 repr 不泄露明文。by AI.Coding"""
    settings = Settings(
        _env_file=None,
        llm_provider="deepseek",
        deepseek_api_key="sk-test-private",
    )

    assert settings.deepseek_api_key is not None
    assert settings.deepseek_api_key.get_secret_value() == "sk-test-private"
    assert "sk-test-private" not in repr(settings)
    assert settings.deepseek_analysis_model == "deepseek-v4-flash"
    assert settings.deepseek_report_model == "deepseek-v4-pro"


def test_deepseek_base_url_requires_https_without_credentials() -> None:
    """DeepSeek 基础地址拒绝明文 HTTP 和 URL 内嵌凭据。by AI.Coding"""
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(_env_file=None, deepseek_base_url="http://api.deepseek.com")
    with pytest.raises(ValidationError, match="用户名或密码"):
        Settings(
            _env_file=None,
            deepseek_base_url="https://user:password@api.deepseek.com",
        )
