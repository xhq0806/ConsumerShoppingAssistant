from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.core.config import Settings


def create_chat_model(settings: Settings, responses: Sequence[str] | None = None) -> BaseChatModel:
    if settings.llm_provider != "fake":
        raise ValueError("M0 仅启用 fake LLM provider。")
    return FakeListChatModel(responses=list(responses or ['{"status":"ok"}']))
