from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Ollama (local LLM — no API key required)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Qdrant (local file-based vector store)
    qdrant_path: str = "./qdrant_data"
    collection_name: str = "presentation_chunks"

    # Retrieval
    top_k: int = 5
    similarity_threshold: float = 0.30

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
