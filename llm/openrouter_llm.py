
from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr

from config import OPENROUTER_API_KEY


class ChatOpenRouter(ChatOpenAI):
    openai_api_key: SecretStr | None = Field(
        alias="api_key",
        default_factory=lambda: OPENROUTER_API_KEY,
    )

    def __init__(self, openai_api_key: str | None = None, **kwargs):
        openai_api_key = OPENROUTER_API_KEY
        super().__init__(
            base_url="https://openrouter.ai/api/v1",
            openai_api_key=openai_api_key,
            **kwargs,
        )
