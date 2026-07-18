from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "MetricMind API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()