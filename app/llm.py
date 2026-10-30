"""LLM factory: one place that turns `LLM_PROVIDER` + `LLM_MODEL` into a browser-use chat model.

browser-use ships its own clients for every provider below, so switching provider is just an
.env change. Gemini is the recommended default: in our production work it was the cheapest
provider that still handles vision (screenshots) well.

Adding a provider = one entry in PROVIDERS + one branch in build_llm(). See README.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from app.config import Settings


@dataclass(frozen=True)
class ProviderInfo:
    default_model: str
    key_env: tuple[str, ...]          # env vars checked (in order) when LLM_API_KEY is empty
    needs_key: bool = True


PROVIDERS: dict[str, ProviderInfo] = {
    # Recommended: cheapest vision-capable option we found for production browser work.
    "google": ProviderInfo("gemini-3.6-flash", ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
    "openai": ProviderInfo("gpt-4.1-mini", ("OPENAI_API_KEY",)),
    "anthropic": ProviderInfo("claude-sonnet-4-5", ("ANTHROPIC_API_KEY",)),
    "azure": ProviderInfo("gpt-4.1-mini", ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_KEY")),
    "groq": ProviderInfo("meta-llama/llama-4-maverick-17b-128e-instruct", ("GROQ_API_KEY",)),
    "openrouter": ProviderInfo("google/gemini-2.5-flash", ("OPENROUTER_API_KEY",)),
    "deepseek": ProviderInfo("deepseek-chat", ("DEEPSEEK_API_KEY",)),
    "mistral": ProviderInfo("mistral-medium-latest", ("MISTRAL_API_KEY",)),
    "ollama": ProviderInfo("qwen2.5vl:7b", (), needs_key=False),
    # Any OpenAI-compatible server (vLLM, LM Studio, Together, Fireworks, ...): set LLM_BASE_URL.
    "openai_compatible": ProviderInfo("", ("OPENAI_API_KEY",), needs_key=False),
    # AWS Bedrock uses the normal AWS credential chain (needs the `aws` extra: uv sync --extra aws).
    "aws": ProviderInfo("anthropic.claude-3-5-sonnet-20240620-v1:0", (), needs_key=False),
}


class LLMConfigError(ValueError):
    pass


def resolve_api_key(settings: Settings) -> Optional[str]:
    if settings.llm_api_key:
        return settings.llm_api_key
    info = PROVIDERS.get(settings.llm_provider)
    for name in info.key_env if info else ():
        if os.getenv(name):
            return os.getenv(name)
    return None


def build_llm(settings: Settings):
    """Return a ready browser-use chat model for the configured provider."""
    provider = settings.llm_provider
    info = PROVIDERS.get(provider)
    if info is None:
        raise LLMConfigError(f"Unknown LLM_PROVIDER '{provider}'. Choose one of: {', '.join(PROVIDERS)}")

    model = settings.llm_model or info.default_model
    if not model:
        raise LLMConfigError(f"LLM_MODEL must be set for provider '{provider}'.")
    key = resolve_api_key(settings)
    if info.needs_key and not key:
        raise LLMConfigError(
            f"No API key for '{provider}'. Set LLM_API_KEY or {' / '.join(info.key_env)} in .env"
        )
    base_url = settings.llm_base_url or None
    temp = {"temperature": settings.llm_temperature} if settings.llm_temperature is not None else {}

    # Imports are local: each browser-use chat class pulls in its provider SDK, which is slow.
    if provider == "google":
        from browser_use import ChatGoogle
        return ChatGoogle(model=model, api_key=key, **temp)
    if provider in ("openai", "openai_compatible"):
        from browser_use import ChatOpenAI
        if provider == "openai_compatible" and not base_url:
            raise LLMConfigError("LLM_BASE_URL is required for openai_compatible.")
        return ChatOpenAI(model=model, api_key=key or "not-needed", base_url=base_url, **temp)
    if provider == "anthropic":
        from browser_use import ChatAnthropic
        return ChatAnthropic(model=model, api_key=key, base_url=base_url, **temp)
    if provider == "azure":
        from browser_use import ChatAzureOpenAI
        return ChatAzureOpenAI(model=model, api_key=key, azure_endpoint=base_url, **temp)
    if provider == "groq":
        from browser_use import ChatGroq
        return ChatGroq(model=model, api_key=key, base_url=base_url, **temp)
    if provider == "openrouter":
        from browser_use import ChatOpenRouter
        kw = {"base_url": base_url} if base_url else {}
        return ChatOpenRouter(model=model, api_key=key, **kw, **temp)
    if provider == "deepseek":
        from browser_use import ChatDeepSeek
        kw = {"base_url": base_url} if base_url else {}
        return ChatDeepSeek(model=model, api_key=key, **kw, **temp)
    if provider == "mistral":
        from browser_use import ChatMistral
        kw = {"base_url": base_url} if base_url else {}
        return ChatMistral(model=model, api_key=key, **kw, **temp)
    if provider == "ollama":
        from browser_use import ChatOllama
        return ChatOllama(model=model, host=base_url or os.getenv("OLLAMA_HOST") or "http://localhost:11434")
    if provider == "aws":
        from browser_use import ChatAWSBedrock
        return ChatAWSBedrock(model=model, aws_region=os.getenv("AWS_REGION"), **temp)

    raise LLMConfigError(f"Provider '{provider}' is listed but not wired in build_llm().")
