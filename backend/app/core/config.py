from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate backend/.env whether execution starts from repo root or backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "MetricMind API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+psycopg://metricmind_user:YOUR_PASSWORD_HERE@localhost:5432/metricmind"

    # Safe SQL Engine Settings
    DEFAULT_QUERY_ROW_LIMIT: int = 100
    MAX_QUERY_ROW_LIMIT: int = 100
    QUERY_TIMEOUT_SECONDS: int = 5

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()