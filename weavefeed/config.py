"""
Centralized configuration management for Weavefeed.

Configuration values are loaded from environment variables (.env)
and exposed through a single immutable Settings object.
"""
from pathlib import Path
from pydantic import Field, model_validator
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
    # Scheduler (times are relative to the RTH open, 09:30 America/New_York)
    # ------------------------------------------------------------------

    # Prediction workflow runs at RTH open + delay. If the scheduler starts
    # late it still runs, up to `delay + grace` minutes after the open.
    # README contract: predictions are made within the first 30 minutes.
    scheduler_delay_minutes: int = Field(default=15, ge=0, le=30)
    scheduler_grace_minutes: int = Field(default=15, ge=0, le=30)

    # ------------------------------------------------------------------
    # Pydantic settings
    # ------------------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _check_scheduler_window(self) -> "Settings":
        if self.scheduler_delay_minutes + self.scheduler_grace_minutes > 30:
            raise ValueError(
                "scheduler_delay_minutes + scheduler_grace_minutes must be <= 30 "
                "(predictions must be generated within 30 minutes of the RTH open)"
            )
        return self


settings = Settings()
