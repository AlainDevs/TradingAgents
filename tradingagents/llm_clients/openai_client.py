import os
from urllib.parse import urlparse
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI with normalized content output.

    The Responses API returns content as a list of typed blocks
    (reasoning, text, etc.). This normalizes to string for consistent
    downstream handling.
    """

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


def _is_native_openai_base_url(base_url: Optional[str]) -> bool:
    """Return whether a configured base URL points at the real OpenAI API."""
    if not base_url:
        return True

    hostname = urlparse(base_url).hostname or ""
    return hostname in {"api.openai.com", "openai.com"}


def _normalize_compatible_base_url(base_url: str) -> str:
    """Ensure OpenAI-compatible providers expose the `/v1` prefix."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"

# Kwargs forwarded from user config to ChatOpenAI
_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "reasoning_effort",
    "api_key", "callbacks", "http_client", "http_async_client",
)

# Provider base URLs and API key env vars
_PROVIDER_CONFIG = {
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI, Ollama, OpenRouter, and xAI providers.

    For native OpenAI models, uses the Responses API (/v1/responses) which
    supports reasoning_effort with function tools across all model families
    (GPT-4.1, GPT-5). Third-party compatible providers (xAI, OpenRouter,
    Ollama) use standard Chat Completions.
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance."""
        llm_kwargs = {"model": self.model}
        is_native_openai = self.provider == "openai" and _is_native_openai_base_url(
            self.base_url
        )

        # Provider-specific base URL and auth
        if self.provider in _PROVIDER_CONFIG:
            base_url, api_key_env = _PROVIDER_CONFIG[self.provider]
            llm_kwargs["base_url"] = base_url
            if api_key_env:
                api_key = os.environ.get(api_key_env)
                if api_key:
                    llm_kwargs["api_key"] = api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif self.base_url:
            if is_native_openai:
                llm_kwargs["base_url"] = self.base_url
            else:
                llm_kwargs["base_url"] = _normalize_compatible_base_url(
                    self.base_url
                )

        # Forward user-provided kwargs
        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # Native OpenAI: use Responses API for consistent behavior across
        # all model families. Custom OpenAI-compatible providers often only
        # implement chat-completions semantics and require SSE streaming.
        if is_native_openai:
            llm_kwargs["use_responses_api"] = True
        elif self.base_url:
            llm_kwargs["streaming"] = True

        return NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return validate_model(self.provider, self.model)
