"""Runtime configuration for TrustShield.

Provider-agnostic LLM config: set ONE of the provider keys in a `.env` file
and the app selects a sensible default model for that provider. Multiple
providers can be configured for fallback — if Groq fails, OpenRouter or
Gemini will be tried.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


_PROVIDER_DEFAULTS = {
    "groq": "groq/openai/gpt-oss-20b",
    "openrouter": "openrouter/openai/gpt-oss-20b",
    "gemini": "gemini/gemini-2.0-flash",
}

_PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if not os.environ.get("TS_TEST") else None,
        env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "TrustShield"
    env: str = "dev"

    llm_provider: str = "groq"
    llm_model: str = ""
    llm_temperature: float = 0.15
    llm_max_tokens: int = 1600
    llm_timeout_seconds: int = 30
    llm_reasoning_effort: str = "low"

    llm_vision_model: str = "groq/meta-llama/llama-4-scout-17b-16e-instruct"

    groq_api_key: str = ""
    openrouter_api_key: str = ""
    gemini_api_key: str = ""

    render_enabled: bool = True
    render_timeout_ms: int = 15000
    render_screenshots: bool = True
    fetch_timeout_seconds: int = 10
    network_enabled: bool = True

    db_path: str = "trustshield.db"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def resolved_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return _PROVIDER_DEFAULTS.get(self.llm_provider, _PROVIDER_DEFAULTS["groq"])

    @property
    def llm_available(self) -> bool:
        key_env = _PROVIDER_KEY_ENV.get(self.llm_provider)
        explicit = getattr(self, f"{self.llm_provider}_api_key", "")
        return bool(explicit or (key_env and os.getenv(key_env)))

    @property
    def fallback_providers(self) -> list[dict]:
        providers = []
        for p in ("openrouter", "gemini"):
            key_env = _PROVIDER_KEY_ENV.get(p)
            explicit = getattr(self, f"{p}_api_key", "")
            if explicit or (key_env and os.getenv(key_env)):
                providers.append({
                    "provider": p,
                    "model": _PROVIDER_DEFAULTS.get(p, ""),
                })
        return providers

    def _provider_of(self, model: str) -> str:
        return model.split("/", 1)[0] if "/" in model else self.llm_provider

    @property
    def vision_available(self) -> bool:
        provider = self._provider_of(self.llm_vision_model)
        key_env = _PROVIDER_KEY_ENV.get(provider)
        explicit = getattr(self, f"{provider}_api_key", "")
        return bool(explicit or (key_env and os.getenv(key_env)))

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def export_provider_key_to_env(self) -> None:
        key_env = _PROVIDER_KEY_ENV.get(self.llm_provider)
        explicit = getattr(self, f"{self.llm_provider}_api_key", "")
        if key_env and explicit and not os.getenv(key_env):
            os.environ[key_env] = explicit


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.export_provider_key_to_env()
    return s
