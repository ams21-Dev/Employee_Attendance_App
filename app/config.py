"""
config.py – Application settings loaded from environment variables.
Uses pydantic-settings so we get automatic env-var parsing and validation.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB connection string – override via MONGO_URI env var
    MONGO_URI: str = "mongodb://localhost:27017"
    # Database name used throughout the app
    DB_NAME: str = "hrone_attendance"

    class Config:
        env_file = ".env"          # reads from .env if present (not committed)
        env_file_encoding = "utf-8"


# Single shared instance – import this everywhere
settings = Settings()
