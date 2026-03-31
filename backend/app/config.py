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

    PUBLIC_DATA_API_KEY: str = ""
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

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


settings = Settings()
