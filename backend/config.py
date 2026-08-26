from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/app.db"
    ingest_token: str = "change-me"
    cors_origins: str = "http://localhost:3000"
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ai-discovery-engine/0.1"
    youtube_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1"
    extract_stub: bool = False
    use_minilm: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
