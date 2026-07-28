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
    ai_provider: str = "real"
    openai_specialist_model: str = "gpt-5.6-luna"
    openai_consolidation_model: str = "gpt-5.6-terra"
    redis_url: str = "redis://redis:6379/0"
    github_token: str = ""
    request_timeout_seconds: float = 15.0

    @property
    def openai_configured(self) -> bool:
        return self.ai_provider == "fake" or bool(self.openai_api_key)


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
