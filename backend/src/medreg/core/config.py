from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_prefix="",
        extra="ignore",
    )

    app_name: str = "MedReg Copilot"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+asyncpg://medreg:medreg@127.0.0.1:55432/medreg"
    )
    minio_endpoint: str = "127.0.0.1:9100"
    minio_access_key: str = "medreg"
    minio_secret_key: str = "medreg-secret"
    minio_bucket: str = "medreg-documents"
    minio_secure: bool = False
    document_max_upload_bytes: int = 20 * 1024 * 1024
    redis_url: str = "redis://127.0.0.1:6479/0"
    qdrant_url: str = "http://127.0.0.1:6433"
    qdrant_collection: str = "medreg_legal_chunks_v1"
    qdrant_api_key: SecretStr | None = None
    neo4j_uri: str = "neo4j://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("medreg-secret")
    neo4j_database: str = "neo4j"
    embedding_dense_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_sparse_model: str = "Qdrant/bm25"
    embedding_cache_dir: str = "~/.cache/medreg-fastembed"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: float = 45.0
    document_parse_stale_after_seconds: int = 300
    official_fetch_timeout_seconds: float = 20.0
    official_fetch_allowed_hosts: list[str] = Field(
        default_factory=lambda: ["samr.gov.cn", "nmpa.gov.cn"]
    )
    app_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5273",
            "http://127.0.0.1:5273",
        ]
    )
    app_allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env != "production":
            return self

        unsafe: list[str] = []
        database = urlparse(self.database_url)
        redis = urlparse(self.redis_url)
        if database.password in {None, "", "medreg"}:
            unsafe.append("DATABASE_URL must contain a non-default password")
        if redis.password in {None, ""}:
            unsafe.append("REDIS_URL must contain a password")
        if self.minio_secret_key in {"", "medreg-secret"}:
            unsafe.append("MINIO_SECRET_KEY must be changed")
        if self.neo4j_password.get_secret_value() in {"", "medreg-secret"}:
            unsafe.append("NEO4J_PASSWORD must be changed")
        if self.qdrant_api_key is None or len(
            self.qdrant_api_key.get_secret_value()
        ) < 16:
            unsafe.append("QDRANT_API_KEY must contain at least 16 characters")
        if not self.app_allowed_hosts or "*" in self.app_allowed_hosts:
            unsafe.append("APP_ALLOWED_HOSTS must explicitly list trusted hosts")
        if unsafe:
            raise ValueError("Unsafe production configuration: " + "; ".join(unsafe))
        return self

    @property
    def cors_origins(self) -> list[str]:
        return self.app_cors_origins

    @property
    def qdrant_api_key_value(self) -> str | None:
        if self.qdrant_api_key is None:
            return None
        return self.qdrant_api_key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
