from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    articles_data_path: Path = Path("data/articles.json")
    articles_cache_ttl_seconds: int = Field(default=3600, gt=0)
    articles_rate_limit_requests: int = Field(default=120, gt=0)
    articles_rate_limit_window_seconds: int = Field(default=60, gt=0)
