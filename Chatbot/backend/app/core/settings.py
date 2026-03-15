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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
