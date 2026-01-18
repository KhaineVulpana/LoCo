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

    async def _ensure_column(conn, table: str, column: str, definition: str) -> None:
        try:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            columns = {row[1] for row in result.fetchall()}
        except Exception as e:
            logger.error("schema_introspection_failed", table=table, error=str(e))
            return

        if column in columns:
            return

        try:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        except Exception as e:
            error = str(e).lower()
            if "duplicate column name" not in error:
                logger.error("schema_migration_failed", table=table, column=column, error=str(e))

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

        await _ensure_column(
            conn,
            table="workspace_policies",
            column="auto_approve_tools",
            definition="TEXT NOT NULL DEFAULT '[]'"
        )

        await _ensure_column(
            conn,
            table="sessions",
            column="folder_id",
            definition="TEXT"
        )

        await _ensure_column(
            conn,
            table="sessions",
            column="agent_id",
            definition="TEXT"
        )

        await _ensure_column(
            conn,
            table="sessions",
            column="model_url",
            definition="TEXT"
        )

        await _ensure_column(
            conn,
            table="sessions",
            column="temperature",
            definition="REAL NOT NULL DEFAULT 0.7"
        )

        await _ensure_column(
            conn,
            table="session_messages",
            column="metadata_json",
            definition="TEXT"
        )

        await conn.commit()

    logger.info("database_initialized")
