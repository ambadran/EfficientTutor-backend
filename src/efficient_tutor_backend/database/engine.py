'''
Database Engine file.
1- Engine: creates and manages TCP Pool connections
2- AsyncSessionLocal: Session Creator (with engine as bind)
3- get_db_session: Dependency to create, yield and manage the life-cycle of a session.
'''
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine, async_sessionmaker
from typing import AsyncGenerator
from ..common.config import settings
from ..common.logger import log

# We define them as None. They will be created by the app's lifespan.
engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

def create_db_engine_and_session_factory():
    """
    Creates the engine and session factory.
    This is called by the app's lifespan event.
    """
    global engine, AsyncSessionLocal
    
    log.info(f"Creating database engine for URL...")
    try:

        # 1. Create the asynchronous engine
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=-1,
            pool_pre_ping=True
        )
        
        # 2. Create the AsyncSessionLocal factory
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        log.info("Async database engine and session factory created successfully.")
    except Exception as e:
        log.critical(f"Failed to create async database engine: {e}", exc_info=True)
        raise

async def dispose_db_engine():
    """Disposes of the engine. Called by the app's lifespan."""
    global engine, AsyncSessionLocal
    if engine:
        await engine.dispose()
        log.info("Database engine disposed.")
    engine = None
    AsyncSessionLocal = None

# 3. The new, robust dependency
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.
    
    This pattern ensures:
    1. A session is created from the factory for each request.
    2. The session is yielded to the route.
    3. The session is auto-committed if the request is successful.
    4. The session is auto-rolled-back if an exception occurs.
    5. The session is always closed after the request.
    """
    if AsyncSessionLocal is None:
        log.error("AsyncSessionLocal is not initialized. App lifespan may not have run.")
        raise RuntimeError("Database session factory is not available.")

    session = AsyncSessionLocal() # Create a new session
    try:
        yield session
        await session.commit()  # Commit on successful request
    except Exception as e:
        await session.rollback() # Rollback on error
        log.error(f"Database session rolled back due to error: {e}")
        raise # Re-raise the exception so FastAPI can handle it
    finally:
        await session.close() # Always close the session
