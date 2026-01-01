"""
Authentication utilities
"""

import secrets
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

TOKEN_FILE = Path.home() / ".loco-agent" / "token"


def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def get_or_create_token() -> str:
    """Get existing token or create a new one"""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        logger.info("token_loaded", file=str(TOKEN_FILE))
        return token
    else:
        token = generate_token()
        TOKEN_FILE.write_text(token)
        TOKEN_FILE.chmod(0o600)  # User read/write only
        logger.info("token_generated", file=str(TOKEN_FILE))
        return token


def verify_token(token: str) -> bool:
    """Verify that the provided token matches the stored token"""
    stored_token = get_or_create_token()
    return secrets.compare_digest(token, stored_token)
