'''

'''
import pytest
import pytest_asyncio
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# --- Import models and services ---
from efficient_tutor_backend.database import models as db_models
from efficient_tutor_backend.database.db_enums import UserRole
from efficient_tutor_backend.services.user_service import (
    UserService, 
    ParentService, 
    StudentService
)

# --- Import Test Constants ---
from tests.constants import (
    TEST_TEACHER_ID, 
    TEST_PARENT_ID, 
    TEST_STUDENT_ID
)


# --- Test Data Fixtures ---
# These fixtures create data in the test session, which is rolled back after each test.

@pytest_asyncio.fixture
async def test_teacher(db_session: AsyncSession) -> db_models.Users:
    """Creates a test teacher user and adds it to the session."""
    teacher = db_models.Users(
        id=TEST_TEACHER_ID,
        email="teacher@test.com",
        name="Test Teacher",
        role=UserRole.TEACHER
        # Add other required fields if any (e.g., hashed_password)
    )
    db_session.add(teacher)
    await db_session.flush()  # Use flush, not commit, as the session will be rolled back
    await db_session.refresh(teacher)
    return teacher

@pytest_asyncio.fixture
async def test_parent(db_session: AsyncSession) -> db_models.Users:
    """Creates a test parent user and adds it to the session."""
    parent = db_models.Users(
        id=TEST_PARENT_ID,
        email="parent@test.com",
        name="Test Parent",
        role=UserRole.PARENT
    )
    db_session.add(parent)
    await db_session.flush()
    await db_session.refresh(parent)
    return parent

@pytest_asyncio.fixture
async def test_student(db_session: AsyncSession) -> db_models.Users:
    """Creates a test student user and adds it to the session."""
    student = db_models.Users(
        id=TEST_STUDENT_ID,
        email="student@test.com",
        name="Test Student",
        role=UserRole.STUDENT
    )
    db_session.add(student)
    await db_session.flush()
    await db_session.refresh(student)
    return student

# --- Test Classes ---

@pytest.mark.asyncio
class TestUserService:
    
    async def test_get_user_by_id(
        self, 
        user_service: UserService, 
        test_teacher: db_models.Users
    ):
        """Tests fetching a user by their ID."""
        user = await user_service.get_user_by_id(test_teacher.id)
        
        assert user is not None
        assert user.id == test_teacher.id
        assert user.email == "teacher@test.com"

    async def test_get_user_by_id_not_found(self, user_service: UserService):
        """Tests that None is returned for a non-existent ID."""
        user = await user_service.get_user_by_id(UUID(int=0)) # Random UUID
        assert user is None

    async def test_get_full_user_by_email(
        self, 
        user_service: UserService, 
        test_teacher: db_models.Users
    ):
        """Tests fetching a user by their email."""
        user = await user_service.get_full_user_by_email("teacher@test.com")
        
        assert user is not None
        assert user.id == test_teacher.id
        assert user.email == "teacher@test.com"

    async def test_get_users_by_ids(
        self, 
        user_service: UserService, 
        test_teacher: db_models.Users,
        test_parent: db_models.Users
    ):
        """Tests fetching a list of users by their IDs."""
        user_ids = [test_teacher.id, test_parent.id]
        users = await user_service.get_users_by_ids(user_ids)
        
        assert len(users) == 2
        user_ids_found = {user.id for user in users}
        assert test_teacher.id in user_ids_found
        assert test_parent.id in user_ids_found


@pytest.mark.asyncio
class TestParentService:

    async def test_get_all_as_teacher(
        self, 
        parents_service: ParentService, 
        test_teacher: db_models.Users,
        test_parent: db_models.Users
    ):
        """Tests that a TEACHER can get all parents."""
        parents = await parents_service.get_all(current_user=test_teacher)
        
        assert len(parents) >= 1
        assert any(p.id == test_parent.id for p in parents)

    async def test_get_all_as_parent_forbidden(
        self, 
        parents_service: ParentService, 
        test_parent: db_models.Users
    ):
        """Tests that a PARENT cannot get all parents (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await parents_service.get_all(current_user=test_parent)
        
        assert e.value.status_code == 403


@pytest.mark.asyncio
class TestStudentService:

    async def test_get_all_as_teacher(
        self, 
        student_service: StudentService, 
        test_teacher: db_models.Users,
        test_student: db_models.Users
    ):
        """Tests that a TEACHER can get all students."""
        students = await student_service.get_all(current_user=test_teacher)
        
        assert len(students) >= 1
        assert any(s.id == test_student.id for s in students)

    async def test_get_all_as_parent(
        self, 
        student_service: StudentService, 
        test_parent: db_models.Users,
        test_student: db_models.Users
    ):
        """Tests that a PARENT can get all students."""
        students = await student_service.get_all(current_user=test_parent)
        
        assert len(students) >= 1
        assert any(s.id == test_student.id for s in students)

    async def test_get_all_as_student_forbidden(
        self, 
        student_service: StudentService, 
        test_student: db_models.Users
    ):
        """Tests that a STUDENT cannot get all students (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await student_service.get_all(current_user=test_student)
        
        assert e.value.status_code == 403
