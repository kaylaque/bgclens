"""BGCLens configuration, loaded from environment variables / .env file."""
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BGCLENS_LLM_", env_file=".env", extra="ignore")

    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"


class BGCLensSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BGCLENS_", env_file=".env", extra="ignore")

    cache_dir: Path = Path.home() / ".cache" / "bgclens"
    llm: LLMSettings = Field(default_factory=LLMSettings)


_settings: BGCLensSettings | None = None


def get_settings() -> BGCLensSettings:
    global _settings
    if _settings is None:
        _settings = BGCLensSettings()
    return _settings
