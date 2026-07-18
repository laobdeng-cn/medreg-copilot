import pytest
from pydantic import ValidationError

from medreg.core.config import Settings


def test_production_configuration_rejects_development_secrets() -> None:
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings(app_env="production", _env_file=None)


def test_production_configuration_accepts_explicit_secrets_and_hosts() -> None:
    settings = Settings(
        app_env="production",
        app_allowed_hosts=["medreg.example.com"],
        database_url="postgresql+asyncpg://medreg:secure123@postgres:5432/medreg",
        redis_url="redis://:secure123@redis:6379/0",
        minio_secret_key="secure-minio-secret",
        neo4j_password="secure-neo4j-secret",
        qdrant_api_key="secure-qdrant-api-key",
        _env_file=None,
    )

    assert settings.app_env == "production"
    assert settings.app_allowed_hosts == ["medreg.example.com"]
    assert settings.qdrant_api_key_value == "secure-qdrant-api-key"
