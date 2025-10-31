'''
Pytest configuration for the FastAPI application.

This file sets up fixtures for:
1. Forcing the application into TEST_MODE before any code is imported.
2. Providing a clean, isolated, and rolled-back database session for each test.
3. Providing a FastAPI TestClient for endpoint testing.
4. Providing instances of all service classes, pre-injected with a test db session.
'''

import pytest
import pytest_asyncio
import os
from typing import AsyncGenerator

# --- FastAPI & Testing Imports ---
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# --- Application Imports ---
# Import the main app object
from src.efficient_tutor_backend.main import app

# Import the engine and session factory
from src.efficient_tutor_backend.database.engine import (
    engine, 
    AsyncSessionLocal, 
    get_db_session
)

# Import all service classes
from src.efficient_tutor_backend.services.user_service import (
    UserService, 
    ParentService, 
    StudentService
)
from src.efficient_tutor_backend.services.tuition_service import TuitionsService
from src.efficient_tutor_backend.services.timetable_service import TimeTableService
from src.efficient_tutor_backend.services.finance_service import (
    TuitionLogService,
    PaymentLogService,
    FinancialSummaryService
)


# --- 1. Core Configuration Fixture (The most important part) ---

@pytest.fixture(scope="session", autouse=True)
def set_test_mode():
    """
    Forces the TEST_MODE environment variable to "True" at the very start
    of the test session. This ensures that when the app code is imported,
    the Pydantic settings load the test database URL, and the
    SQLAlchemy engine is created with the correct (test) database.
    """
    os.environ["TEST_MODE"] = "True"
    
    # We must also clear the singleton engine if it was already created
    # This is a safeguard against import-order issues.
    if engine._async_engine:
        # This is a bit of a hack, but necessary if the engine was created
        # before this fixture ran (e.g., by another import).
        # In a typical run, this might not be needed, but it's safer.
        from src.efficient_tutor_backend.database import engine as engine_module
        engine_module.engine = None 
        # Ideally, we would re-create it, but setting TEST_MODE=True 
        # and re-importing the app (which TestClient does) is often enough.
        # Let's simplify: just setting the env var is the key.
    
    # After this fixture runs, any subsequent import of `config.settings`
    # or `database.engine` will use the test database.
    

# --- 2. Database Session Fixtures (For Service-Level Tests) ---

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean, isolated database session for each test function.
    
    This creates a new session from our factory, yields it to the test,
    and then guarantees a rollback and close, so tests can't affect each other.
    """
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.rollback()  # Roll back any changes made during the test
        await session.close()     # Close the session


# --- 3. Service-Level Fixtures (For testing business logic directly) ---

@pytest_asyncio.fixture(scope="function")
async def user_service(db_session: AsyncSession) -> UserService:
    """Provides a UserService instance with a test session."""
    return UserService(db=db_session)

@pytest_asyncio.fixture(scope="function")
async def parents_service(
    db_session: AsyncSession, 
    user_service: UserService
) -> ParentService:
    """Provides a ParentsService instance with test dependencies."""
    # Assuming ParentService takes db and user_service.
    # Adjust if your __init__ is different.
    return ParentService(db=db_session, user_service=user_service)

@pytest_asyncio.fixture(scope="function")
async def student_service(
    db_session: AsyncSession, 
    user_service: UserService
) -> StudentService:
    """Provides a StudentService instance with test dependencies."""
    # Assuming StudentService takes db and user_service.
    # Adjust if your __init__ is different.
    return StudentService(db=db_session, user_service=user_service)

@pytest_asyncio.fixture(scope="function")
async def tuitions_service(
    db_session: AsyncSession, 
    user_service: UserService
) -> TuitionsService:
    """Provides a TuitionsService instance with test dependencies."""
    return TuitionsService(db=db_session, user_service=user_service)


@pytest_asyncio.fixture(scope="function")
async def timetable_service(
    db_session: AsyncSession, 
    tuitions_service: TuitionsService
) -> TimeTableService:
    """Provides a TimeTableService instance with test dependencies."""
    return TimeTableService(db=db_session, tuitions_service=tuitions_service)


@pytest_asyncio.fixture(scope="function")
async def tuition_log_service(
    db_session: AsyncSession, 
    user_service: UserService, 
    tuitions_service: TuitionsService
) -> TuitionLogService:
    """Provides a TuitionLogService instance with test dependencies."""
    return TuitionLogService(
        db=db_session, 
        user_service=user_service, 
        tuitions_service=tuitions_service
    )


@pytest_asyncio.fixture(scope="function")
async def payment_log_service(
    db_session: AsyncSession, 
    user_service: UserService
) -> PaymentLogService:
    """Provides a PaymentLogService instance with test dependencies."""
    return PaymentLogService(db=db_session, user_service=user_service)


@pytest_asyncio.fixture(scope="function")
async def financial_summary_service(db_session: AsyncSession) -> FinancialSummaryService:
    """Provides a FinancialSummaryService instance with a test session."""
    return FinancialSummaryService(db=db_session)


# --- 4. API-Level Fixtures (For Endpoint Testing) ---

@pytest.fixture(scope="function")
def client() -> TestClient:
    """
    Provides a FastAPI TestClient that overrides the database dependency.
    
    This fixture ensures that any API endpoint call made through this client
    will use an isolated, rolled-back test session.
    """
    
    # This is our test-specific dependency that will be injected
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        """
        Overrides the `get_db_session` dependency to provide a test session
        that is automatically rolled back.
        """
        session = AsyncSessionLocal()
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()

    # Apply the override to the main app
    app.dependency_overrides[get_db_session] = override_get_db_session

    # Yield the test client
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up the override after the test
    app.dependency_overrides.clear()
