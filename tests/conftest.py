'''
Pytest configuration for the FastAPI application.

This file sets up fixtures for:
1. Forcing the application into TEST_MODE before any code is imported.
2. Providing a clean, isolated, and rolled-back database session for each test.
3. Providing a FastAPI TestClient for endpoint testing.
4. Providing instances of all service classes, pre-injected with a test db session.
'''

import pytest
import os
from typing import AsyncGenerator

# --- FastAPI & Testing Imports ---
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import select

# --- Constant Imports ----
from tests.constants import (
    TEST_PARENT_ID,
    TEST_TEACHER_ID,
    TEST_STUDENT_ID,
    TEST_PARENT_IDS,
    TEST_TUITION_ID,
    TEST_TUITION_LOG_ID_SCHEDULED,
    TEST_TUITION_LOG_ID_CUSTOM,
    TEST_PAYMENT_LOG_ID
)

# --- Application Imports ---
from src.efficient_tutor_backend.main import app
from src.efficient_tutor_backend.common.config import settings
from src.efficient_tutor_backend.database.engine import get_db_session
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import (
    UserService, ParentService, StudentService
)
from src.efficient_tutor_backend.services.tuition_service import TuitionService
from src.efficient_tutor_backend.services.timetable_service import TimeTableService
from src.efficient_tutor_backend.services.finance_service import (
    TuitionLogService,
    PaymentLogService,
    FinancialSummaryService
)


@pytest.fixture(scope="session")
def anyio_backend():
    """
    Override the default 'anyio_backend' fixture.
    1. Forces the backend to 'asyncio' (solves 'trio' error).
    2. Promotes the scope to 'session' (solves 'ScopeMismatch').
    """
    return "asyncio"


@pytest.fixture(scope="function")
def client() -> TestClient:
    """
    The core fixture for all tests.
    
    1. Sets TEST_MODE=True to be 100% safe.
    2. Runs the app's lifespan, which creates the *real* database engine.
    3. Overrides the `get_db_session` dependency to use a transaction
       that gets rolled back after every test for isolation.
    """
    # Force test mode, just in case.
    # Note: Your config uses TEST_MODE, not TESTING_MODE.
    os.environ["TEST_MODE"] = "True"
    
    # Verify the settings loaded correctly
    assert settings.TEST_MODE is True, \
        "TEST_MODE was not set to True! Check your .env file or environment."

    # This is our new test-specific dependency override
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        # The app's lifespan (triggered by TestClient) has already
        # run and created the global AsyncSessionLocal factory.
        from src.efficient_tutor_backend.database.engine import AsyncSessionLocal
        
        if AsyncSessionLocal is None:
             raise RuntimeError("TestClient failed to initialize the app's lifespan.")

        session = AsyncSessionLocal()
        try:
            yield session
        finally:
            await session.rollback() # This is the key to test isolation
            await session.close()

    # Apply the override to the main app
    app.dependency_overrides[get_db_session] = override_get_db_session

    # This 'with' block runs the app's startup lifespan,
    # which creates the engine and session factory.
    with TestClient(app) as test_client:
        yield test_client
    
    # The app's shutdown lifespan runs here, and we clear the override.
    app.dependency_overrides.clear()


# --- 2. Function-Scoped Session Fixture (For Service Tests) ---

@pytest.fixture(scope="function")
async def db_session(client: TestClient) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a single, isolated, rolled-back database session for
    service-level tests.
    
    It depends on the 'client' fixture to ensure the engine is
    already created by the app's lifespan.
    """
    from src.efficient_tutor_backend.database.engine import AsyncSessionLocal
    
    if AsyncSessionLocal is None:
        raise RuntimeError("Session factory not initialized by client fixture.")

    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()

# --- 5. SERVICE FIXTURES ---
# These now just depend on the clean `db_session` fixture.

@pytest.fixture(scope="function")
def user_service(db_session: AsyncSession) -> UserService:
    return UserService(db=db_session)

@pytest.fixture(scope="function")
def parents_service(db_session: AsyncSession) -> ParentService:
    return ParentService(db=db_session)

@pytest.fixture(scope="function")
def student_service(db_session: AsyncSession) -> StudentService:
    return StudentService(db=db_session)

@pytest.fixture(scope="function")
def tuition_service_sync() -> TuitionService:
    """
    allow me to test synchronous methods without the stupid warning
    """
    return TuitionService(db=None, user_service=None)

@pytest.fixture(scope="function")
def tuition_service(db_session: AsyncSession, user_service: UserService) -> TuitionService:
    return TuitionService(db=db_session, user_service=user_service)

@pytest.fixture(scope="function")
def timetable_service(
    db_session: AsyncSession, tuition_service: TuitionService
) -> TimeTableService:
    return TimeTableService(db=db_session, tuition_service=tuition_service)

@pytest.fixture(scope="function")
def timetable_service_sync() -> TimeTableService:
    """
    Provides a lightweight, *synchronous* instance of TimeTableService
    for testing utility methods that don't need a real db or other services.
    """
    # Pass None for dependencies, as the formatting methods don't use them.
    return TimeTableService(db=None, tuition_service=None)

@pytest.fixture(scope="function")
def tuition_log_service(
    db_session: AsyncSession, 
    user_service: UserService, 
    tuition_service: TuitionService
) -> TuitionLogService:
    return TuitionLogService(
        db=db_session, 
        user_service=user_service, 
        tuition_service=tuition_service
    )

@pytest.fixture(scope="function")
async def payment_log_service(
    db_session: AsyncSession, 
    user_service: UserService
) -> PaymentLogService:
    """Provides a PaymentLogService instance with test dependencies."""
    return PaymentLogService(
        db=db_session, 
        user_service=user_service
    )

@pytest.fixture(scope="function")
def payment_log_service_sync() -> PaymentLogService:
    """
    Provides a lightweight, *synchronous* instance of PaymentLogService
    for testing utility methods that don't need a real db or other services.
    """
    # We pass None for dependencies because the _format_payment_log_for_api
    # method doesn't use them.
    return PaymentLogService(db=None, user_service=None)

@pytest.fixture(scope="function")
def financial_summary_service(db_session: AsyncSession) -> FinancialSummaryService:
    return FinancialSummaryService(db=db_session)

# --- 6. DATA FIXTURES ---
# Your fixtures to fetch data are perfect.
# Note: They are now `async` and must depend on `db_session`.

@pytest.fixture(scope="function")
async def test_teacher_orm(db_session: AsyncSession) -> db_models.Teachers: # <-- Changed type
    """Fetches the main test teacher ORM object from the test DB."""
    # --- CHANGED ---
    # Get the specific 'Teachers' class, not the base 'Users' class
    teacher = await db_session.get(db_models.Teachers, TEST_TEACHER_ID)
    # ---------------
    
    assert teacher is not None, f"Test teacher with ID {TEST_TEACHER_ID} not found in DB."
    return teacher

@pytest.fixture(scope="function")
async def test_parent_orm(db_session: AsyncSession) -> db_models.Parents: # <-- Changed type
    """Fetches the main test parent ORM object from the test DB."""
    # --- CHANGED ---
    parent = await db_session.get(db_models.Parents, TEST_PARENT_ID)
    # ---------------

    assert parent is not None, f"Test parent with ID {TEST_PARENT_ID} not found in DB."
    return parent

@pytest.fixture(scope="function")
async def test_student_orm(db_session: AsyncSession) -> db_models.Students: # <-- Changed type
    """Fetches the main test student ORM object from the test DB."""
    # --- CHANGED ---
    student = await db_session.get(db_models.Students, TEST_STUDENT_ID)
    # ---------------
    
    assert student is not None, f"Test student with ID {TEST_STUDENT_ID} not found in DB."
    return student

@pytest.fixture(scope="function")
async def test_parents_orm_list(db_session: AsyncSession) -> list[db_models.Parents]: # <-- Changed type
    """Fetches a list of test parent ORM objects from the test DB."""
    # --- CHANGED ---
    # Select from 'Parents' directly
    stmt = select(db_models.Parents).where(db_models.Parents.id.in_(TEST_PARENT_IDS))
    # ---------------
    
    parents = (await db_session.scalars(stmt)).all()
    assert len(parents) == len(TEST_PARENT_IDS), "Not all test parents were found in DB."
    return parents

@pytest.fixture(scope="function")
async def test_tuition_orm(db_session: AsyncSession) -> db_models.Tuitions:
    tuition = await db_session.get(db_models.Tuitions, TEST_TUITION_ID)
    assert tuition is not None, f"Test tuition with ID {TEST_TUITION_ID} not found."
    return tuition

@pytest.fixture(scope="function")
async def tuition_log_scheduled(db_session: AsyncSession) -> db_models.TuitionLogs:
    """Fetches a known scheduled tuition log from the test DB."""
    
    # --- THE FIX ---
    # We must eagerly load the charges relationship to prevent
    # a lazy-load (MissingGreenlet) error in the test.
    stmt = select(db_models.TuitionLogs).options(
        selectinload(db_models.TuitionLogs.tuition_log_charges)
    ).filter(db_models.TuitionLogs.id == TEST_TUITION_LOG_ID_SCHEDULED)
    
    result = await db_session.execute(stmt)
    log = result.scalars().first()
    # ---------------

    assert log is not None, f"Scheduled test log {TEST_TUITION_LOG_ID_SCHEDULED} not found in DB."
    assert log.create_type == "SCHEDULED"
    return log

@pytest.fixture(scope="function")
async def tuition_log_custom(db_session: AsyncSession) -> db_models.TuitionLogs:
    """Fetches a known custom tuition log from the test DB."""
    
    # --- THE FIX ---
    # We apply the same fix here for consistency.
    stmt = select(db_models.TuitionLogs).options(
        selectinload(db_models.TuitionLogs.tuition_log_charges)
    ).filter(db_models.TuitionLogs.id == TEST_TUITION_LOG_ID_CUSTOM)
    
    result = await db_session.execute(stmt)
    log = result.scalars().first()
    # ---------------

    assert log is not None, f"Custom test log {TEST_TUITION_LOG_ID_CUSTOM} not found in DB."
    assert log.create_type == "CUSTOM"
    return log

@pytest.fixture(scope="function")
async def payment_log_orm(db_session: AsyncSession) -> db_models.PaymentLogs:
    """Fetches a known payment log from the test DB."""
    # We must eagerly load the relationships to prevent
    # lazy-load (MissingGreenlet) errors in the service methods.
    stmt = select(db_models.PaymentLogs).options(
        selectinload(db_models.PaymentLogs.parent),
        selectinload(db_models.PaymentLogs.teacher)
    ).filter(db_models.PaymentLogs.id == TEST_PAYMENT_LOG_ID)
    
    result = await db_session.execute(stmt)
    log = result.scalars().first()
    
    assert log is not None, f"Test payment log {TEST_PAYMENT_LOG_ID} not found in DB."
    return log
