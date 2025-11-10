'''

'''
import pytest
from uuid import UUID
from fastapi import HTTPException
from datetime import time

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import (
    UserService, 
    ParentService, 
    StudentService
)
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import SubjectEnum
from tests.constants import TEST_TEACHER_ID, TEST_PARENT_ID, TEST_STUDENT_ID

from pprint import pp as pprint

# --- Test Classes ---

@pytest.mark.anyio
class TestUserService:
    
    async def test_get_teacher_user_by_id(
        self, 
        user_service: UserService, 
        test_teacher_orm: db_models.Teachers  # <-- Use the new fixture
    ):
        """Tests fetching a user by their ID."""
        user = await user_service.get_user_by_id(test_teacher_orm.id)

        print(type(user))
        pprint(user.__dict__)
        
        assert user is not None
        assert user.id == test_teacher_orm.id
        assert user.email == test_teacher_orm.email

    async def test_get_parent_user_by_id(
        self, 
        user_service: UserService, 
        test_parent_orm: db_models.Parents  # <-- Use the new fixture
    ):
        """Tests fetching a user by their ID."""
        user = await user_service.get_user_by_id(test_parent_orm.id)

        print(type(user))
        pprint(user.__dict__)
        
        assert user is not None
        assert user.id == test_parent_orm.id
        assert user.email == test_parent_orm.email

    async def test_get_student_user_by_id(
        self, 
        user_service: UserService, 
        test_student_orm: db_models.Students # <-- Use the new fixture
    ):
        """Tests fetching a user by their ID."""
        user = await user_service.get_user_by_id(test_student_orm.id)

        print(type(user))
        pprint(user.__dict__)
        pprint(user.student_subjects[0].__dict__)
        pprint(user.student_availability_intervals[0].__dict__)
        
        assert user is not None
        assert user.id == test_student_orm.id
        assert user.email == test_student_orm.email


    async def test_get_user_by_id_not_found(self, user_service: UserService):
        """Tests that None is returned for a non-existent ID."""
        user = await user_service.get_user_by_id(UUID(int=0)) # Random UUID
        assert user is None

    async def test_get_teacher_user_by_email(
        self, 
        user_service: UserService, 
        test_teacher_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests fetching a user by their email."""
        user = await user_service.get_user_by_email(test_teacher_orm.email)

        print(type(user))
        pprint(user.__dict__)
        
        assert user is not None
        assert user.id == test_teacher_orm.id

    async def test_get_parent_user_by_email(
        self, 
        user_service: UserService, 
        test_parent_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests fetching a user by their email."""
        user = await user_service.get_user_by_email(test_parent_orm.email)

        print(type(user))
        pprint(user.__dict__)
        
        assert user is not None
        assert user.id == test_parent_orm.id

    async def test_get_student_user_by_email(
        self, 
        user_service: UserService, 
        test_student_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests fetching a user by their email."""
        user = await user_service.get_user_by_email(test_student_orm.email)

        print(type(user))
        pprint(user.__dict__)
        pprint(user.student_subjects[0].__dict__)
        pprint(user.student_availability_intervals[0].__dict__)
 
        
        assert user is not None
        assert user.id == test_student_orm.id

    async def test_get_users_by_ids(
        self, 
        user_service: UserService, 
        test_teacher_orm: db_models.Users,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Users
    ):
        """Tests fetching a list of users by their IDs."""
        user_ids = [test_teacher_orm.id, test_parent_orm.id, test_student_orm.id]
        users = await user_service.get_users_by_ids(user_ids)

        print("One of the users full data:")
        pprint(users[0].__dict__)

        assert len(users) == 3
        user_ids_found = {user.id for user in users}
        assert test_teacher_orm.id in user_ids_found
        assert test_parent_orm.id in user_ids_found


@pytest.mark.anyio
class TestParentService:

    async def test_get_all_as_teacher(
        self, 
        parents_service: ParentService, 
        test_teacher_orm: db_models.Users, # <-- Use the new fixture
        test_parent_orm: db_models.Users   # <-- Use the new fixture
    ):
        """Tests that a TEACHER can get all parents."""
        parents = await parents_service.get_all(current_user=test_teacher_orm)

        print(f"Found {len(parents)} parents for teacher '{test_teacher_orm.first_name} {test_teacher_orm.last_name}':\n{[parent.first_name for parent in parents]}")
        
        assert len(parents) >= 1
        assert any(p.id == test_parent_orm.id for p in parents)

    async def test_get_all_as_parent_forbidden(
        self, 
        parents_service: ParentService, 
        test_parent_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests that a PARENT cannot get all parents (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await parents_service.get_all(current_user=test_parent_orm)
        
        assert e.value.status_code == 403

    async def test_get_all_as_student_forbidden(
        self, 
        parents_service: ParentService, 
        test_student_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests that a PARENT cannot get all parents (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await parents_service.get_all(current_user=test_student_orm)
        
        assert e.value.status_code == 403



@pytest.mark.anyio
class TestStudentService:

    async def test_get_all_as_teacher(
        self, 
        student_service: StudentService, 
        test_teacher_orm: db_models.Users, # <-- Use the new fixture
        test_student_orm: db_models.Users  # <-- Use the new fixture
    ):
        """Tests that a TEACHER can get all students."""
        students = await student_service.get_all(current_user=test_teacher_orm)
       
        print(f"Found {len(students)} students for teacher '{test_teacher_orm.first_name} {test_teacher_orm.last_name}':\n{[student.first_name for student in students]}")

        assert len(students) >= 1
        assert type(students[0]) == db_models.Students
        assert any(s.id == test_student_orm.id for s in students)

    async def test_get_all_as_parent(
        self, 
        student_service: StudentService, 
        test_parent_orm: db_models.Users, # <-- Use the new fixture
        test_student_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests that a PARENT can get all students."""
        students = await student_service.get_all(current_user=test_parent_orm)

        print(f"Found {len(students)} students for Parent '{test_parent_orm.first_name} {test_parent_orm.last_name}':\n{[student.first_name for student in students]}")
        
        assert len(students) >= 1
        assert type(students[0]) == db_models.Students
        assert any(s.id == test_student_orm.id for s in students)

    async def test_get_all_as_student_forbidden(
        self, 
        student_service: StudentService, 
        test_student_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests that a STUDENT cannot get all students (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await student_service.get_all(current_user=test_student_orm)
        
        assert e.value.status_code == 403

    # --- Tests for create_student ---

    @pytest.fixture
    def valid_student_data(self) -> dict:
        """Provides a valid dictionary for creating a student."""
        return {
            "email": "pytest.student@example.com",
            "first_name": "Pytest",
            "last_name": "Student",
            "timezone": "UTC",
            "parent_id": TEST_PARENT_ID,
            "student_subjects": [
                {
                    "subject": SubjectEnum.PHYSICS,
                    "lessons_per_week": 2,
                    "shared_with_student_ids": [TEST_STUDENT_ID]
                }
            ],
            "student_availability_intervals": [
                {
                    "day_of_week": 1,
                    "start_time": time(9, 0),
                    "end_time": time(17, 0),
                    "availability_type": "school"
                }
            ]
        }

    async def test_create_student_as_teacher_happy_path(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests successful student creation by a Teacher."""
        print("\n--- Testing create_student as TEACHER (Happy Path) ---")
        
        create_model = user_models.StudentCreate(**valid_student_data)
        
        new_student = await student_service.create_student(create_model, test_teacher_orm)
        
        assert isinstance(new_student, user_models.StudentRead)
        assert new_student.email == create_model.email
        assert new_student.first_name == "Pytest"
        assert new_student.parent_id == TEST_PARENT_ID
        
        # Verify relational data
        assert len(new_student.student_subjects) == 1
        assert new_student.student_subjects[0].subject == SubjectEnum.PHYSICS
        assert new_student.student_subjects[0].shared_with_student_ids == [TEST_STUDENT_ID]
        
        assert len(new_student.student_availability_intervals) == 1
        assert new_student.student_availability_intervals[0].day_of_week == 1

        # Check the underlying DB object for generated password
        db_student = await student_service.get_user_by_id(new_student.id)
        assert db_student.generated_password is not None

        print("--- Successfully created student (API model) ---")
        pprint(new_student.model_dump())

    async def test_create_student_as_parent_happy_path(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests successful student creation by a Parent."""
        print("\n--- Testing create_student as PARENT (Happy Path) ---")
        
        # Ensure the parent is creating their own child
        valid_student_data["parent_id"] = test_parent_orm.id
        valid_student_data["email"] = "pytest.student.parent@example.com" # different email to avoid conflict
        create_model = user_models.StudentCreate(**valid_student_data)
        
        new_student = await student_service.create_student(create_model, test_parent_orm)
        
        assert isinstance(new_student, user_models.StudentRead)
        assert new_student.email == create_model.email
        assert new_student.parent_id == test_parent_orm.id
        
        print("--- Successfully created student (API model) ---")
        pprint(new_student.model_dump())

    async def test_create_student_as_student_forbidden(
        self,
        student_service: StudentService,
        test_student_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Student is FORBIDDEN from creating a student."""
        print("\n--- Testing create_student as STUDENT (Forbidden) ---")
        
        # Ensure the test email isn't used by other tests
        valid_student_data["email"] = "student.forbidden@example.com" 
        create_model = user_models.StudentCreate(**valid_student_data)
        
        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_student_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_student_duplicate_email(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that creating a student with an existing email fails."""
        print("\n--- Testing create_student with duplicate email ---")
        
        valid_student_data["email"] = test_student_orm.email  # Use an existing email
        create_model = user_models.StudentCreate(**valid_student_data)
        
        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_teacher_orm)
            
        assert e.value.status_code == 400
        assert "Email already registered" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_student_non_existent_parent(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests creating a student with a parent_id that does not exist."""
        print("\n--- Testing create_student with non-existent parent ---")
        
        valid_student_data["email"] = "nonexistent.parent@example.com" # different email to avoid conflict
        valid_student_data["parent_id"] = UUID(int=0) # Random, non-existent UUID
        create_model = user_models.StudentCreate(**valid_student_data)
        
        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_teacher_orm)
                
            assert e.value.status_code == 404
            assert "not found" in e.value.detail
            print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")


    async def test_create_student_with_minimal_data(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests creating a student with empty subjects and availability."""
        print("\n--- Testing create_student with minimal data ---")
        
        valid_student_data["student_subjects"] = []
        valid_student_data["student_availability_intervals"] = []
        valid_student_data["email"] = "minimal.student@example.com"
        
        create_model = user_models.StudentCreate(**valid_student_data)
        
        new_student = await student_service.create_student(create_model, test_teacher_orm)
        
        assert isinstance(new_student, user_models.StudentRead)
        assert new_student.email == "minimal.student@example.com"
        assert len(new_student.student_subjects) == 0
        assert len(new_student.student_availability_intervals) == 0
        
        print("--- Successfully created student with minimal data ---")
        pprint(new_student.model_dump())
