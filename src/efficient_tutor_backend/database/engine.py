'''
Database Engine file.
1- Engine: creates and manages TCP Pool connections
2- AsyncSessionLocal: Session Creator (with engine as bind)
3- get_db_session: Dependency to create, yield and manage the life-cycle of a session.
'''
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from ..common.config import settings
from ..common.logger import log

# 1. Create the asynchronous engine
try:
    engine = create_async_engine(
        settings.database_url,
        echo=False,  # Set to True to see generated SQL statements
        pool_size = 5,  # No. of core tcp sessions always opened and ready
        max_overflow = 10,  # max no. temporary pool connections if core is exhausted, closed after traffic frees
        pool_timeout = 30, # 30 sec wait if all 15 pools busy and non were freed
        pool_recycle = -1, # never auto-restart a pool connection after a specific amount of time
        pool_pre_ping = True  # runs a simple 'SELECT 1' with every checkout (new API request)
    )
    log.info("Async database engine created successfully.")
except Exception as e:
    log.critical(f"Failed to create async database engine: {e}", exc_info=True)
    raise

# 2. Create the AsyncSessionLocal factory
# This is the new, correct way to do it
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # Good default for async
    autocommit=False,       # Good default
    autoflush=False,        # Good default
)

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
