from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR.parent.parent

class Settings(BaseSettings):
    # Cau hinh CSDL va he thong
    DB_HOST: str = "127.0.0.1"
    DB_USER: str = "root"
    DB_PASSWORD: str = "Namle123456"
    DB_NAME: str = "goodreads"
    MYSQL_POOL_SIZE: int = 10
    MYSQL_POOL_TIMEOUT_SECONDS: int = 5
    TRENDING_CACHE_TTL_SECONDS: int = 60
    SQLITE_PATH: Path = BASE_DIR / "books.db"

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_DIR / ".env"), str(BASE_DIR / ".env")),
        extra="ignore",
    )

settings = Settings()
if settings.DB_HOST == "mysql":
    settings.DB_HOST = "127.0.0.1"

