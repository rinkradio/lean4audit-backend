"""
Centralized app configuration. Loaded from environment variables (.env).
Never hardcode secrets here.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 2880

    CORS_ORIGINS: str = "http://localhost:5173"

    INITIAL_ADMIN_EMPLOYEE_ID: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "Principal@lean"
    INITIAL_ADMIN_FULL_NAME: str = "Principal Consultant"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
