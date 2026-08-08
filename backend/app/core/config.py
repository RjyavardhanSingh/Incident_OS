from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Incident OS"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://incident_os:incident_os_dev@localhost:5433/incident_os_dev"
    )
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "investigation-workers"
    demo_database_url: str = (
        "postgresql+psycopg://incident_os:incident_os_dev@localhost:5433/incident_os_dev"
    )
    demo_redis_url: str = "redis://localhost:6379/0"
    demo_kafka_bootstrap_servers: str = "localhost:9092"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
