from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    env: str = Field(default="dev")

    # API
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)

    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Storage
    sqlite_path: str = Field(default="app.db", alias="SQLITE_PATH")

    # Config
    clinics_config_path: str = Field(default="app/config/clinics.yaml", alias="CLINICS_CONFIG_PATH")

    # Agent
    max_turns: int = Field(default=10, alias="MAX_TURNS")

    # OpenAI
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Auth
    auth_secret: str = Field(default="dev-auth-secret", alias="AUTH_SECRET")
    otp_ttl_minutes: int = Field(default=10, alias="OTP_TTL_MINUTES")
    auth_session_hours: int = Field(default=24, alias="AUTH_SESSION_HOURS")

    # Email
    email_sender: str = Field(default="no-reply@queueiq.local", alias="EMAIL_SENDER")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")

    # RAG / PostgreSQL
    rag_database_url: str | None = Field(default=None, alias="RAG_DATABASE_URL")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    rag_enable_auto_init: bool = Field(default=True, alias="RAG_ENABLE_AUTO_INIT")
    rag_vector_dimensions: int = Field(default=768, alias="RAG_VECTOR_DIMENSIONS")
    rag_enable_embeddings: bool = Field(default=True, alias="RAG_ENABLE_EMBEDDINGS")
    rag_embedding_model: str = Field(default="nomic-embed-text", alias="RAG_EMBEDDING_MODEL")

    # Local model provider abstraction
    rag_model_provider: str = Field(default="ollama", alias="RAG_MODEL_PROVIDER")
    rag_active_model: str = Field(default="gemma3_4b", alias="RAG_ACTIVE_MODEL")
    rag_model_specs: dict[str, dict[str, str]] = Field(default_factory=dict, alias="RAG_MODEL_SPECS")
    rag_ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="RAG_OLLAMA_BASE_URL")
    rag_openai_base_url: str = Field(default="http://127.0.0.1:8005/v1", alias="RAG_OPENAI_BASE_URL")
    rag_openai_api_key: str = Field(default="local-dev-key", alias="RAG_OPENAI_API_KEY")
    enable_prompt_logging: bool = Field(default=False, alias="ENABLE_PROMPT_LOGGING")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
