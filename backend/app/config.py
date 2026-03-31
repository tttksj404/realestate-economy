from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 데이터베이스 설정
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/realestate"

    # Redis 설정 (캐싱, 세션 등)
    REDIS_URL: str = "redis://localhost:6379/0"

    # ChromaDB 벡터 스토어 경로
    CHROMADB_PATH: str = "./chroma_db"

    # 공공데이터포털 API 키 (국토부 실거래가 API 등)
    PUBLIC_DATA_API_KEY: str = ""

    # 네이버 부동산 API 크레덴셜
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    # 로컬 LLM 모델 경로 (HuggingFace 모델 또는 파인튜닝된 모델)
    LLM_MODEL_PATH: str = "beomi/Llama-3-Open-Ko-8B"

    # 임베딩 모델 (다국어 E5 large - 한국어 지원)
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-large"

    # CORS 허용 오리진 목록
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # 앱 메타
    APP_NAME: str = "부동산 경제 분석 서비스"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # LLM 추론 설정
    LLM_MAX_NEW_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.7
    LLM_TOP_P: float = 0.9

    # RAG 설정
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.7

    # 데이터 수집 스케줄 (cron 표현식)
    DATA_COLLECT_CRON: str = "0 2 * * *"  # 매일 새벽 2시


settings = Settings()
