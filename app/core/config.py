import secrets
from typing import Annotated

from pydantic import (
    AnyUrl,
    BeforeValidator,
    computed_field,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.vault_loader import load_config

load_config()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    # API Configuration
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # Server Configuration
    SERVER_NAME: str = "SDA API"
    SERVER_HOST: str = "http://localhost"
    SERVER_PORT: int = 8081

    # CORS Configuration
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str,
        BeforeValidator(lambda x: x.split(",") if isinstance(x, str) else x),
    ] = []

    # Project Configuration
    PROJECT_NAME: str = "SDA API"

    # Database Configuration (Postgres / Supabase)
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "sda"
    POSTGRES_PASSWORD: str = "sda123"
    POSTGRES_DB: str = "sda"
    # Full connection string override (Supabase). Nếu set, dùng thẳng thay cho POSTGRES_* ở trên.
    DATABASE_URL: str | None = None

    # Redis Configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Neo4j (Knowledge Graph) Configuration
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "sda-neo4j"

    # MinIO Configuration
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "sda-files"
    MINIO_PUBLIC_BUCKET_NAME: str = "sda-public"
    MINIO_PUBLIC_URL: str = "http://localhost:9000"  # Public URL for permanent links (internal Docker network)
    LOG_LEVEL: str = "DEBUG"

    # Gmail API Configuration
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""

    # Admin Configuration
    ADMIN_USER_IDS: list = [2, 20]  # Default admin is user_id=1; override via ADMIN_USER_IDS env var (comma-separated)
    ADMIN_USERNAME: str = "admin"  # Admin login username
    ADMIN_PASSWORD: str = "admin123"  # Admin login password

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return str(
            MultiHostUrl.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def PROXY_URL(self) -> str:
        """Construct proxy URL from PROXY_HOST and PROXY_PORT."""
        return f"http://{self.PROXY_HOST}:{self.PROXY_PORT}"


settings = Settings()
