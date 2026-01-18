"""
Configuration settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import secrets


class Settings(BaseSettings):
    # Server
    VERSION: str = "0.1.0"
    PROTOCOL_VERSION: str = "1.0.0"
    PORT: int = 3199
    DEBUG: bool = False  # Disable to reduce log noise (SQLAlchemy query echo)

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
    RAG_CONTEXT_TOKENS: int = 1200
    WORKSPACE_CONTEXT_TOKENS: int = 1200
    ACE_CONTEXT_TOKENS: int = 800
    TEST_LOOP_MAX_ATTEMPTS: int = 3

    # Workspace path resolution (comma/semicolon-separated roots)
    WORKSPACE_SEARCH_ROOTS: str = ""

    # Remote docs ingestion
    REMOTE_DOCS_ENABLED: bool = True
    REMOTE_DOCS_REFRESH_HOURS: int = 24

    # Web tools
    SERPAPI_API_KEY: Optional[str] = None
    SERPAPI_BASE_URL: str = "https://serpapi.com/search.json"
    SERPAPI_ENGINE: str = "google"
    WEB_FETCH_USER_AGENT: str = "LoCo-Agent/0.1"

    # Uploads
    UPLOADS_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 50

    # Repo hosting integrations
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    GITLAB_TOKEN: Optional[str] = None
    GITLAB_API_BASE_URL: str = "https://gitlab.com/api/v4"
    JIRA_BASE_URL: Optional[str] = None
    JIRA_EMAIL: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None

    # Optional: serve a built web UI from the backend (SPA dist folder)
    UI_DIST_PATH: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()
