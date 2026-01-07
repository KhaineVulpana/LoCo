"""
Configuration settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    # Server
    VERSION: str = "0.1.0"
    PROTOCOL_VERSION: str = "1.0.0"
    PORT: int = 3199
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    AUTH_TOKEN: Optional[str] = None  # Generated on first run
    AUTH_ENABLED: bool = False  # Disable auth by default for local use

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./loco_agent.db"

    # Vector Store
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None

    # Model
    MODEL_PROVIDER: str = "ollama"  # ollama, vllm, llamacpp
    MODEL_NAME: str = "qwen3-coder:30b-a3b-q4_K_M"
    MODEL_URL: str = "http://localhost:11434"

    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    # FIXED #13: Don't hard-code dimensions, get from model at runtime via embedding_manager.get_dimensions()

    # Context
    MAX_CONTEXT_TOKENS: int = 16384
    MAX_RESPONSE_TOKENS: int = 4096

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
