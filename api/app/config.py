from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """إعدادات التطبيق. كل الحقول تُقرأ من البيئة (أو .env عند التشغيل محلياً)."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str = "postgresql://rag:rag@db:5432/rag"
    upload_dir: str = "/data/uploads"
    max_upload_bytes: int = 50 * 1024 * 1024

    # Ollama يعمل على الهوست، لا داخل docker-compose
    ollama_url: str = "http://host.docker.internal:11434"
    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_model: str = "karnak-6b"
    llm_api_key: str = "ollama"
    embed_model: str = "qwen3-embedding:0.6b"


settings = Settings()
