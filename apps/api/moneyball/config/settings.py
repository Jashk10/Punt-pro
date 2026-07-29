from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    base_currency: str = "AUD"

    database_url: str = "postgresql+psycopg://moneyball:moneyball_dev_password@localhost:5433/moneyball"
    redis_url: str = "redis://localhost:6380/0"
    celery_broker_url: str = "redis://localhost:6380/1"
    celery_result_backend: str = "redis://localhost:6380/2"

    jwt_secret: str = "change_me_dev_only_change_me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    admin_email: str = "admin@example.com"
    admin_password: str = "change_me_dev_only"

    squiggle_user_agent: str = "moneyball-dev"
    football_data_api_key: str | None = None
    api_football_key: str | None = None
    odds_api_key: str | None = None

    api_key_encryption_secret: str = "change_me_generate_a_real_fernet_key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
