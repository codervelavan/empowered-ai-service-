from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env.local", ".env"), extra="ignore")
    service_auth_token: str = ""
    portal_auth_token: str = ""
    frappe_auth_token: str = ""
    portal_callback_url: str = ""
    portal_callback_secret: str = ""
    openai_api_key: str = ""
    # Any OpenAI-compatible endpoint. Leave blank for OpenAI itself; set to
    # https://openrouter.ai/api/v1 to route through OpenRouter (whose keys
    # start `sk-or-v1-`). Model ids differ per provider -- OpenRouter needs
    # the `vendor/model` form, e.g. `google/gemma-4-26b-a4b-it:free`.
    openai_base_url: str = ""
    ai_provider: str = "real"
    # NOTE: gpt-5.6-luna / gpt-5.6-terra (the prior defaults here) do not
    # exist on any provider's model catalog as of this writing -- confirmed
    # against both OpenAI's and OpenRouter's live model lists. Defaulting to
    # a model confirmed (live) to actually honor strict json_schema
    # structured outputs, which this service depends on -- most models
    # silently return prose instead of erroring, which is exactly the
    # failure mode the n8n pipeline this replaces used to hit.
    openai_specialist_model: str = "gpt-4o-mini"
    openai_consolidation_model: str = "gpt-4o-mini"
    # Retried once, only on a structured-output compliance failure (the
    # primary model returned prose, or wrapped valid JSON in something
    # _json_completion's markdown-fence strip couldn't fix) — not a general
    # retry-on-any-error path, since Celery's own retry/backoff already
    # covers transient failures. See evaluation.py's _json_completion.
    openai_fallback_model: str = "gpt-4o-mini"
    redis_url: str = "redis://redis:6379/0"
    github_token: str = ""
    request_timeout_seconds: float = 15.0

    @property
    def openai_configured(self) -> bool:
        return self.ai_provider == "fake" or bool(self.openai_api_key)


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
