"""
Application configuration loaded from environment variables.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from .env and environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    UNSTRUCTURED_API_KEY: str
    UNSTRUCTURED_API_URL: str = "https://api.unstructuredapp.io/general/v0/general"
    OPENAI_API_KEY: str
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "nfra_compliance"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION_REGULATIONS: str = "regulatory_frameworks"
    CHROMA_COLLECTION_DOCUMENTS: str = "financial_documents"
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    LLM_MODEL: str = "gpt-4.1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8888


@lru_cache
def get_settings() -> Settings:
    """
    Return cached application settings. Uses LRU cache to avoid re-loading from env.
    """
    return Settings()
