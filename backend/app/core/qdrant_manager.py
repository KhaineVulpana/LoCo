"""
Qdrant Manager - Handles automatic startup and connection
"""

import subprocess
import time
import httpx
import structlog
from pathlib import Path

logger = structlog.get_logger()


class QdrantManager:
    """Manages Qdrant container lifecycle"""

    def __init__(self, host: str = "localhost", port: int = 6333):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"

    async def ensure_running(self) -> bool:
        """
        Ensure Qdrant is running, start it if not.
        Returns True if Qdrant is available, False otherwise.
        """
        # Check if Qdrant is already running
        if await self.is_healthy():
            logger.info("qdrant_already_running")
            return True

        # Try to start Qdrant via Docker Compose
        logger.info("starting_qdrant")
        if self.start_qdrant():
            # Wait for it to become healthy
            return await self.wait_for_healthy(timeout=30)

        logger.error("failed_to_start_qdrant")
        return False

    async def is_healthy(self) -> bool:
        """Check if Qdrant is healthy"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/",
                    timeout=2.0
                )
                return response.status_code == 200
        except Exception:
            return False

    def start_qdrant(self) -> bool:
        """Start Qdrant using Docker Compose"""
        try:
            # Find docker-compose.yml
            compose_file = Path(__file__).parent.parent.parent.parent / "docker-compose.yml"

            if not compose_file.exists():
                logger.error("docker_compose_file_not_found", path=str(compose_file))
                return False

            # Start only the qdrant service
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "up", "-d", "qdrant"],
                capture_output=True,
                text=True,
                cwd=compose_file.parent
            )

            if result.returncode == 0:
                logger.info("qdrant_started_successfully")
                return True
            else:
                logger.error("docker_compose_failed",
                           stdout=result.stdout,
                           stderr=result.stderr)
                return False

        except FileNotFoundError:
            logger.error("docker_not_found",
                        message="Docker is not installed or not in PATH")
            return False
        except Exception as e:
            logger.error("failed_to_start_qdrant", error=str(e))
            return False

    async def wait_for_healthy(self, timeout: int = 30) -> bool:
        """Wait for Qdrant to become healthy"""
        start_time = time.time()
        logger.info("waiting_for_qdrant_to_be_healthy", timeout=timeout)

        while time.time() - start_time < timeout:
            if await self.is_healthy():
                logger.info("qdrant_is_healthy")
                return True

            await asyncio.sleep(1)

        logger.error("qdrant_health_check_timeout")
        return False


# Import asyncio at module level
import asyncio
