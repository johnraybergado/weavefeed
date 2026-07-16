"""
Centralized configuration management for Weavefeed.

Configuration values are loaded from environment variables (.env)
and exposed through a single immutable Settings object.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------

    postgres_db: str = "weavefeed"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ------------------------------------------------------------------
    # Market APIs
    # ------------------------------------------------------------------

    finnhub_api_key: str = ""
    finnhub_request_delay: float = 3.0  # Seconds to wait between API calls

    # ------------------------------------------------------------------
    # RSS Sources
    # ------------------------------------------------------------------

    marketwatch_rss_url: str = (
        "https://feeds.content.dowjones.io/public/rss/mw_topstories"
    )

    yahoo_finance_rss_url: str = (
        "https://finance.yahoo.com/news/rssindex"
)
    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    llm_provider: str = "google"
    llm_model: str = "gemini-3.5-flash"

    google_api_key: str = ""

    # ------------------------------------------------------------------
    # Pydantic settings
    # ------------------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
