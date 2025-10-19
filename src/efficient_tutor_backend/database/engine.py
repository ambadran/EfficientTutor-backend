'''

'''
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from ..common.config import settings
from ..common.logger import log

# Create the asynchronous engine using the DATABASE_URL from settings
try:
    engine = create_async_engine(
        settings.database_url,
        echo=False,  # Set to True to see generated SQL statements
        future=True
    )
    log.info("Async database engine created successfully.")
except Exception as e:
    log.critical(f"Failed to create async database engine: {e}", exc_info=True)
    raise

# Create a configured "Session" class. This is our session factory.
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency that provides a database session to each request.
    It ensures the session is properly closed after the request is finished.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
