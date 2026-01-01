"""
Database connection and initialization
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import structlog
from pathlib import Path

from app.core.config import settings

logger = structlog.get_logger()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database with schema"""
    logger.info("initializing_database")

    async with engine.begin() as conn:
        # Read and execute schema
        schema_path = Path(__file__).parent.parent.parent / "schema.sql"

        if schema_path.exists():
            schema_sql = schema_path.read_text()

            # Split by semicolon and execute each statement
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement:
                    try:
                        await conn.execute(text(statement))
                    except Exception as e:
                        # Ignore table already exists errors
                        if "already exists" not in str(e).lower():
                            logger.error("schema_error", statement=statement[:100], error=str(e))

        await conn.commit()

    logger.info("database_initialized")
