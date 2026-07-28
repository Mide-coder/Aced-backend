from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./aced.db"

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Paystack
    PAYSTACK_SECRET: str = ""

    # Sentry
    SENTRY_DSN: str = ""

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "aced-uploads"

    # Celery / Redis (Upstash Free Tier) [E004-S04]
    REDIS_URL: str = "redis://localhost:6379/0"

    # WhatsApp Cloud API [E004-S04]
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # Frontend URL (for payment callbacks and public profiles)
    FRONTEND_URL: str = "http://localhost:3000"


settings = Settings()
