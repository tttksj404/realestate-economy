import secrets
import warnings
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/realestate"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Chroma can run either embedded (path) or as a separate server (host/port).
    CHROMADB_PATH: str = "./chroma_db"
    CHROMADB_HOST: str = ""
    CHROMADB_PORT: int = 8000

    # 국토부 실거래가 API 키 (유형별 별도 인증키)
    PUBLIC_DATA_API_KEY_APT: str = ""        # 아파트 매매
    PUBLIC_DATA_API_KEY_SMALL: str = ""      # 단독/다가구
    PUBLIC_DATA_API_KEY_TOGETHER: str = ""   # 연립다세대
    PUBLIC_DATA_API_KEY_OFFICE: str = ""     # 오피스텔

    # 온비드 공매 API
    ONBID_API_KEY: str = ""

    LLM_MODEL_PATH: str = "beomi/Llama-3-Open-Ko-8B"
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-large"

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    APP_NAME: str = "Real Estate Economy Service"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

    SECRET_KEY: str = ""
    API_KEY: str = ""

    LOG_LEVEL: str = "INFO"

    LLM_MAX_NEW_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.7
    LLM_TOP_P: float = 0.9

    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.7

    DATA_COLLECT_CRON: str = "0 2 * * *"

    ENABLE_SCHEDULER: bool = True
    SCHEDULER_HOUR: int = 6
    SCHEDULER_MINUTE: int = 0
    SCHEDULER_TIMEZONE: str = "Asia/Seoul"
    SCHEDULER_SOURCE: str = "all"
    SCHEDULER_MONTHS: int = 3

    WEB_CONCURRENCY: int = 1

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    def validate_production(self) -> None:
        if not self.is_production:
            return
        if not self.SECRET_KEY or self.SECRET_KEY == "change_me_to_a_long_random_string":
            raise ValueError("SECRET_KEY must be set in production. Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")

    def get_secret_key(self) -> str:
        if self.SECRET_KEY:
            return self.SECRET_KEY
        warnings.warn("SECRET_KEY not set — using random key (sessions lost on restart)", stacklevel=2)
        return secrets.token_urlsafe(48)


settings = Settings()
settings.validate_production()
