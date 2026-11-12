import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR.parent.parent

def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.getenv("RUNNING_IN_DOCKER") == "1"

class Settings(BaseSettings):
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "change-me"
    DB_NAME: str = "goodreads_web"
    MYSQL_POOL_SIZE: int = 10
    MYSQL_POOL_TIMEOUT_SECONDS: int = 5
    TRENDING_CACHE_TTL_SECONDS: int = 60
    SQLITE_PATH: Path = BASE_DIR / "books.db"

    JWT_SECRET: str = "change-me-jwt-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_ENABLED: bool = True
    RECOMMENDATION_CACHE_TTL_SECONDS: int = 600
    CATEGORIES_CACHE_TTL_SECONDS: int = 300
    STATS_CACHE_TTL_SECONDS: int = 120

    CORS_ORIGINS: str = "http://127.0.0.1:8090,http://localhost:8090,http://127.0.0.1:3000,http://localhost:3000"
    RATE_LIMIT_AUTH_PER_MIN: int = 30
    RATE_LIMIT_RECOMMEND_PER_MIN: int = 60

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

settings = Settings()
if settings.DB_HOST == "mysql" and not _running_in_docker():
    settings.DB_HOST = "127.0.0.1"
