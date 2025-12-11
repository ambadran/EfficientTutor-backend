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
from datetime import time
import uuid
from unittest.mock import AsyncMock, MagicMock

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
    TEST_PAYMENT_LOG_ID,
    TEST_NOTE_ID,
    TEST_UNRELATED_TEACHER_ID,
    TEST_UNRELATED_PARENT_ID,
    TEST_TUITION_ID_NO_LINK,
    TEST_ADMIN_ID,
    TEST_NORMAL_ADMIN_ID,
    TEST_DELETABLE_TEACHER_ID,
    FIN_TEACHER_A_ID, FIN_TEACHER_B_ID,
    FIN_PARENT_A_ID, FIN_PARENT_B_ID,
    FIN_STUDENT_A1_ID, FIN_STUDENT_A2_ID, FIN_STUDENT_B1_ID
)

# --- Application Imports ---
from src.efficient_tutor_backend.main import app
from src.efficient_tutor_backend.common.config import settings
from src.efficient_tutor_backend.database.engine import get_db_session
from src.efficient_tutor_backend.database.db_enums import (
        SubjectEnum,
        UserRole,
        AdminPrivilegeType,
        EducationalSystemEnum
        )

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import (
    UserService, 
    ParentService, 
    StudentService, 
    TeacherService,
    AdminService
)
from src.efficient_tutor_backend.services.tuition_service import TuitionService
from src.efficient_tutor_backend.services.timetable_service import TimeTableService
from src.efficient_tutor_backend.services.finance_service import (
    TuitionLogService,
    PaymentLogService,
    FinancialSummaryService
)
from src.efficient_tutor_backend.services.notes_service import NotesService
from src.efficient_tutor_backend.services.geo_service import GeoService


@pytest.fixture(scope="session")
def anyio_backend():
    """
    Override the default 'anyio_backend' fixture.
    1. Forces the backend to 'asyncio' (solves 'trio' error).
    2. Promotes the scope to 'session' (solves 'ScopeMismatch').
    """
    return "asyncio"


@pytest.fixture(scope="function")
def client(mock_geo_service: GeoService) -> TestClient:
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
    
    # Create a mock for GeoService and override it
    app.dependency_overrides[GeoService] = lambda: mock_geo_service

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
def parents_service(db_session: AsyncSession, mock_geo_service: GeoService) -> ParentService:
    return ParentService(db=db_session, geo_service=mock_geo_service)

@pytest.fixture(scope="function")
def mock_geo_service() -> GeoService:
    """Provides a mock GeoService instance."""
    mock_service = MagicMock(spec=GeoService)
    # Configure the mock's get_location_info method
    mock_service.get_location_info = AsyncMock(return_value={
        "timezone": "America/New_York",
        "currency": "USD"
    })
    return mock_service

@pytest.fixture(scope="function")
def student_service(db_session: AsyncSession) -> StudentService:
    return StudentService(db=db_session)

@pytest.fixture(scope="function")
def teacher_service(db_session: AsyncSession, mock_geo_service: GeoService) -> TeacherService:
    return TeacherService(db=db_session, geo_service=mock_geo_service)

@pytest.fixture(scope="function")
def admin_service(db_session: AsyncSession, mock_geo_service: GeoService) -> AdminService:
    return AdminService(db=db_session, geo_service=mock_geo_service)

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
    db_session: AsyncSession, user_service: UserService
) -> TimeTableService:
    return TimeTableService(db=db_session, user_service=user_service)

@pytest.fixture(scope="function")
def timetable_service_sync() -> TimeTableService:
    """
    Provides a lightweight, *synchronous* instance of TimeTableService
    for testing utility methods that don't need a real db or other services.
    """
    # Pass None for dependencies, as the formatting methods don't use them.
    return TimeTableService(db=None, user_service=None)

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
def financial_summary_service(db_session: AsyncSession, tuition_log_service: TuitionLogService) -> FinancialSummaryService:
    return FinancialSummaryService(db=db_session, tuition_log_service=tuition_log_service)

@pytest.fixture(scope="function")
async def notes_service(db_session: AsyncSession, user_service: UserService) -> NotesService:
    """Provides a NotesService instance with a test session."""
    return NotesService(db=db_session, user_service=user_service)

# --- 6. DATA FIXTURES ---
# Your fixtures to fetch data are perfect.
# Note: They are now `async` and must depend on `db_session`.

@pytest.fixture(scope="function")
async def test_admin_orm(db_session: AsyncSession) -> db_models.Admins: # <-- Changed type
    """Fetches the main test admin ORM object from the test DB."""
    # --- CHANGED ---
    # Get the specific 'Admin's class, not the base 'Users' class
    admin = await db_session.get(db_models.Admins, TEST_ADMIN_ID)
    # ---------------
    
    assert admin is not None, f"Test admin with ID {TEST_ADMIN_ID} not found in DB."
    return admin

@pytest.fixture(scope="function")
async def test_normal_admin_orm(db_session: AsyncSession) -> db_models.Admins:
    """Fetches the normal admin user ORM object from the seeded data."""
    admin = await db_session.get(db_models.Admins, TEST_NORMAL_ADMIN_ID)
    assert admin is not None, f"Test normal admin with ID {TEST_NORMAL_ADMIN_ID} not found in DB."
    return admin

@pytest.fixture(scope="function")
async def test_teacher_orm(db_session: AsyncSession) -> db_models.Teachers: # <-- Changed type
    """Fetches the main test teacher ORM object from the test DB."""
    # --- CHANGED ---
    # Get the specific 'Teachers' class, not the base 'Users' class
    stmt = select(db_models.Teachers).options(
        selectinload(db_models.Teachers.teacher_specialties),
        selectinload(db_models.Teachers.availability_intervals)
    ).filter(db_models.Teachers.id == TEST_TEACHER_ID)
    
    result = await db_session.execute(stmt)
    teacher = result.scalars().first()
    # ---------------
    
    assert teacher is not None, f"Test teacher with ID {TEST_TEACHER_ID} not found in DB."
    return teacher

@pytest.fixture(scope="function")
async def test_student_orm(db_session: AsyncSession) -> db_models.Students: # <-- Changed type
    """Fetches the main test student ORM object from the test DB."""
    # --- CHANGED ---
    stmt = select(db_models.Students).options(
        selectinload(db_models.Students.availability_intervals),
        selectinload(db_models.Students.student_subjects)
    ).filter(db_models.Students.id == TEST_STUDENT_ID)
    
    result = await db_session.execute(stmt)
    student = result.scalars().first()
    # ---------------
    
    assert student is not None, f"Test student with ID {TEST_STUDENT_ID} not found in DB."
    return student

@pytest.fixture(scope="function")
async def test_parent_orm(db_session: AsyncSession) -> db_models.Parents:
    """Fetches the main test parent ORM object, EAGERLY LOADING students."""
    
    # --- THE FIX ---
    # Eagerly load the 'students' relationship to prevent lazy-load errors
    stmt = select(db_models.Parents).options(
        selectinload(db_models.Parents.students)
    ).filter(db_models.Parents.id == TEST_PARENT_ID)
    
    result = await db_session.execute(stmt)
    parent = result.scalars().first()
    # ---------------

    assert parent is not None, f"Test parent with ID {TEST_PARENT_ID} not found in DB."
    return parent

@pytest.fixture(scope="function")
async def test_tuition_orm(db_session: AsyncSession) -> db_models.Tuitions:
    """Fetches the main test tuition, EAGERLY LOADING the meeting_link."""
    
    # --- THE FIX ---
    # We must eagerly load the relationship to prevent lazy-load errors
    stmt = select(db_models.Tuitions).options(
        selectinload(db_models.Tuitions.meeting_link),
        selectinload(db_models.Tuitions.tuition_template_charges)
    ).filter(db_models.Tuitions.id == TEST_TUITION_ID)
    
    result = await db_session.execute(stmt)
    tuition = result.scalars().first()
    # ---------------
    
    assert tuition is not None, f"Test tuition with ID {TEST_TUITION_ID} not found in DB."
    assert tuition.meeting_link is not None, \
        f"Test tuition {TEST_TUITION_ID} must have a meeting link for update/delete tests."
    return tuition

@pytest.fixture(scope="function")
async def test_tuition_orm_no_link(db_session: AsyncSession) -> db_models.Tuitions:
    """
    Fetches a known tuition from the test DB that does NOT have a meeting link.
    Used for testing 'create' logic.
    """
    
    # --- ALSO FIX THIS one for consistency ---
    stmt = select(db_models.Tuitions).options(
        selectinload(db_models.Tuitions.meeting_link) # Eager load (even if it's None)
    ).filter(db_models.Tuitions.id == TEST_TUITION_ID_NO_LINK)
    
    tuition = (await db_session.scalars(stmt)).first()
    # ---------------
    
    assert tuition is not None, f"Test tuition {TEST_TUITION_ID_NO_LINK} not found."
    assert tuition.meeting_link is None, \
        f"Test tuition {TEST_TUITION_ID_NO_LINK} IS NOT clean. It already has a meeting link."
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

@pytest.fixture(scope="function")
async def test_note_orm(db_session: AsyncSession) -> db_models.Notes:
    """
    Fetches the main test note, eager-loading its relationships
    to prevent lazy-load errors and for use in API formatting.
    """
    stmt = select(db_models.Notes).options(
        selectinload(db_models.Notes.teacher),
        selectinload(db_models.Notes.student)
    ).filter(db_models.Notes.id == TEST_NOTE_ID)
    
    result = await db_session.execute(stmt)
    note = result.scalars().first()
    
    # Assertions to ensure your test data is correct
    assert note is not None, f"Test note {TEST_NOTE_ID} not found in DB."
    assert note.teacher_id == TEST_TEACHER_ID, "Test note is not owned by TEST_TEACHER_ID"
    assert note.student_id == TEST_STUDENT_ID, "Test note is not for TEST_STUDENT_ID"
    return note

@pytest.fixture(scope="function")
async def test_unrelated_teacher_orm(db_session: AsyncSession) -> db_models.Teachers:
    """Fetches a teacher who is NOT the owner of the test note."""
    teacher = await db_session.get(db_models.Teachers, TEST_UNRELATED_TEACHER_ID)
    assert teacher is not None, f"Test unrelated teacher {TEST_UNRELATED_TEACHER_ID} not found in DB."
    assert teacher.id != TEST_TEACHER_ID, "TEST_UNRELATED_TEACHER_ID is the same as TEST_TEACHER_ID"
    return teacher

@pytest.fixture(scope="function")
async def test_deletable_teacher_orm(db_session: AsyncSession) -> db_models.Teachers:
    """Fetches a teacher with no relations, specifically for testing deletion."""
    teacher = await db_session.get(db_models.Teachers, TEST_DELETABLE_TEACHER_ID)
    assert teacher is not None, f"Test deletable teacher {TEST_DELETABLE_TEACHER_ID} not found in DB."
    return teacher

@pytest.fixture(scope="function")
async def test_unrelated_parent_orm(db_session: AsyncSession) -> db_models.Parents:
    """Fetches a parent who is NOT the owner of the test note."""
    parent = await db_session.get(db_models.Parents, TEST_UNRELATED_PARENT_ID)
    assert parent is not None, f"Test unrelated parent {TEST_UNRELATED_PARENT_ID} not found in DB."
    assert parent.id != TEST_PARENT_ID, "TEST_UNRELATED_PARENT_ID is the same as TEST_PARENT_ID"
    return parent 

@pytest.fixture
def valid_student_data() -> dict:
    """
    Provides a valid, JSON-serializable dictionary for creating a student,
    mimicking a payload from a frontend client.
    """
    return {
        "first_name": "Pytest",
        "last_name": "Student",
        "parent_id": str(TEST_PARENT_ID),
        "cost": 50.0,
        "status": "Alpha",
        "min_duration_mins": 60,
        "max_duration_mins": 120,
        "grade": 10,
        "educational_system": 'IGCSE',
        "student_subjects": [
            {
                "subject": SubjectEnum.PHYSICS.value,
                "lessons_per_week": 2,
                "grade": 10,
                "shared_with_student_ids": [str(TEST_STUDENT_ID)],
                "teacher_id": str(TEST_TEACHER_ID),
                "educational_system": EducationalSystemEnum.IGCSE.value
            }
        ],
        "availability_intervals": [
            {
                "day_of_week": 1,
                "start_time": time(9, 0).isoformat(),
                "end_time": time(17, 0).isoformat(),
                "availability_type": "school"
            }
        ]
    }

# --- FINANCIAL SANDBOX FIXTURES ---

@pytest.fixture(scope="function")
async def fin_teacher_a(db_session: AsyncSession) -> db_models.Teachers:
    stmt = select(db_models.Teachers).options(
        selectinload(db_models.Teachers.teacher_specialties)
    ).filter(db_models.Teachers.id == FIN_TEACHER_A_ID)
    result = await db_session.execute(stmt)
    teacher = result.scalars().first()
    assert teacher is not None, f"Fin Teacher A {FIN_TEACHER_A_ID} not found."
    return teacher

@pytest.fixture(scope="function")
async def fin_teacher_b(db_session: AsyncSession) -> db_models.Teachers:
    stmt = select(db_models.Teachers).options(
        selectinload(db_models.Teachers.teacher_specialties)
    ).filter(db_models.Teachers.id == FIN_TEACHER_B_ID)
    result = await db_session.execute(stmt)
    teacher = result.scalars().first()
    assert teacher is not None, f"Fin Teacher B {FIN_TEACHER_B_ID} not found."
    return teacher

@pytest.fixture(scope="function")
async def fin_parent_a(db_session: AsyncSession) -> db_models.Parents:
    stmt = select(db_models.Parents).options(
        selectinload(db_models.Parents.students)
    ).filter(db_models.Parents.id == FIN_PARENT_A_ID)
    result = await db_session.execute(stmt)
    parent = result.scalars().first()
    assert parent is not None, f"Fin Parent A {FIN_PARENT_A_ID} not found."
    return parent

@pytest.fixture(scope="function")
async def fin_parent_b(db_session: AsyncSession) -> db_models.Parents:
    stmt = select(db_models.Parents).options(
        selectinload(db_models.Parents.students)
    ).filter(db_models.Parents.id == FIN_PARENT_B_ID)
    result = await db_session.execute(stmt)
    parent = result.scalars().first()
    assert parent is not None, f"Fin Parent B {FIN_PARENT_B_ID} not found."
    return parent

@pytest.fixture(scope="function")
async def fin_student_a1(db_session: AsyncSession) -> db_models.Students:
    stmt = select(db_models.Students).options(
        selectinload(db_models.Students.student_subjects)
    ).filter(db_models.Students.id == FIN_STUDENT_A1_ID)
    result = await db_session.execute(stmt)
    student = result.scalars().first()
    assert student is not None, f"Fin Student A1 {FIN_STUDENT_A1_ID} not found."
    return student

@pytest.fixture(scope="function")
async def fin_student_a2(db_session: AsyncSession) -> db_models.Students:
    stmt = select(db_models.Students).options(
        selectinload(db_models.Students.student_subjects)
    ).filter(db_models.Students.id == FIN_STUDENT_A2_ID)
    result = await db_session.execute(stmt)
    student = result.scalars().first()
    assert student is not None, f"Fin Student A2 {FIN_STUDENT_A2_ID} not found."
    return student

@pytest.fixture(scope="function")
async def fin_student_b1(db_session: AsyncSession) -> db_models.Students:
    stmt = select(db_models.Students).options(
        selectinload(db_models.Students.student_subjects)
    ).filter(db_models.Students.id == FIN_STUDENT_B1_ID)
    result = await db_session.execute(stmt)
    student = result.scalars().first()
    assert student is not None, f"Fin Student B1 {FIN_STUDENT_B1_ID} not found."
    return student


