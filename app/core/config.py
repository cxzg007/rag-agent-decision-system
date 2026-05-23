from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "RAG Agent Decision System"
    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "agent_chunks"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://agent:agent@127.0.0.1:15432/agent?connect_timeout=2"

    llm_provider: str = "mock"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = 30.0
    openai_api_key: str | None = None
    dashscope_api_key: str | None = None
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    rerank_provider: str = "sentence-transformers"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_batch_size: int = 16
    retrieval_candidate_multiplier: int = 8
    knn_num_candidates_multiplier: int = 20
    dependency_check_timeout_seconds: float = 2.0
    require_api_key: bool = False
    api_key: str | None = None
    max_question_length: int = 2000
    max_session_id_length: int = 128
    allowed_tool_scopes: str = "retrieval,memory,planning,mission"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
