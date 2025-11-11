'''

'''
import pytest
from uuid import UUID
from fastapi import HTTPException
from datetime import time
from decimal import Decimal

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import (
    UserService, 
    ParentService, 
    StudentService
)
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, UserRole
from src.efficient_tutor_backend.common.security_utils import HashedPassword
from unittest.mock import MagicMock
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

    async def test_create_parent_happy_path(
        self,
        parents_service: ParentService,
        user_service: UserService,
        mock_geo_service: MagicMock # Add mock_geo_service fixture
    ):
        """Tests the successful creation of a new parent user."""
        print("\n--- Testing create_parent (Happy Path) ---")
        parent_data = user_models.ParentCreate(
            email="new.parent@example.com",
            password="strongpassword123",
            first_name="New",
            last_name="Parent",
            timezone="UTC", # This will be overridden by geo_service
            currency="USD"  # This will be overridden by geo_service
        )
        ip_address = "1.2.3.4" # Dummy IP for testing

        # --- ACT ---
        created_parent = await parents_service.create_parent(parent_data, ip_address)

        # --- ASSERT ---
        # 1. Check the returned Pydantic model
        assert isinstance(created_parent, user_models.ParentRead)
        assert created_parent.email == parent_data.email
        assert created_parent.first_name == parent_data.first_name
        assert created_parent.role == UserRole.PARENT
        assert created_parent.is_first_sign_in is True
        assert created_parent.timezone == "America/New_York" # Assert against mocked value
        assert created_parent.currency == "USD" # Assert against mocked value
        # A new parent should have no students
        # assert created_parent.students == [] # This is not in ParentRead model

        # 2. Verify the user exists in the database
        db_user = await user_service.get_user_by_id(created_parent.id)
        assert db_user is not None
        assert db_user.email == parent_data.email
        assert isinstance(db_user, db_models.Parents)
        assert db_user.timezone == "America/New_York" # Assert against mocked value
        assert db_user.currency == "USD" # Assert against mocked value

        # 3. Verify the password was hashed correctly
        assert HashedPassword.verify(parent_data.password, db_user.password) is True
        assert db_user.password != parent_data.password

        # 4. Verify geo_service was called
        mock_geo_service.get_location_info.assert_called_once_with(ip_address)

        print("--- Successfully created parent ---")
        pprint(created_parent.model_dump())

    async def test_create_parent_duplicate_email(
        self,
        parents_service: ParentService,
        test_teacher_orm: db_models.Users,
    ):
        """Tests that creating a parent with a duplicate email raises a 400 error."""
        print("\n--- Testing create_parent with duplicate email ---")
        parent_data = user_models.ParentCreate(
            email=test_teacher_orm.email,  # Use an existing email from another user
            password="anotherpassword",
            first_name="Duplicate",
            last_name="Email",
            timezone="UTC",
            currency="EUR"
        )
        ip_address = "5.6.7.8" # Dummy IP

        # --- ACT & ASSERT ---
        with pytest.raises(HTTPException) as exc_info:
            await parents_service.create_parent(parent_data, ip_address)

        assert exc_info.value.status_code == 400
        assert "Email already registered" in exc_info.value.detail
        print(f"--- Correctly raised HTTPException: {exc_info.value.status_code} ---")


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


    # --- Tests for update_parent ---

    async def test_update_parent_as_self(
        self,
        parents_service: ParentService,
        test_parent_orm: db_models.Parents,
        user_service: UserService
    ):
        """Tests that a parent can successfully update their own profile."""
        print("\n--- Testing update_parent as self ---")
        update_data = user_models.ParentUpdate(
            first_name="UpdatedFirstName",
            currency="EUR"
        )

        updated_parent = await parents_service.update_parent(
            parent_id=test_parent_orm.id,
            update_data=update_data,
            current_user=test_parent_orm
        )

        assert isinstance(updated_parent, user_models.ParentRead)
        assert updated_parent.id == test_parent_orm.id
        assert updated_parent.first_name == "UpdatedFirstName"
        assert updated_parent.currency == "EUR"
        # Ensure other fields are unchanged
        assert updated_parent.last_name == test_parent_orm.last_name

        # Verify in DB
        db_user = await user_service.get_user_by_id(test_parent_orm.id)
        assert db_user.first_name == "UpdatedFirstName"
        assert db_user.currency == "EUR"

    async def test_update_parent_as_teacher(
        self,
        parents_service: ParentService,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers,
        user_service: UserService
    ):
        """Tests that a teacher can successfully update a parent's profile."""
        print("\n--- Testing update_parent as teacher ---")
        update_data = user_models.ParentUpdate(
            email="new.parent.email@example.com",
            timezone="Europe/London"
        )

        updated_parent = await parents_service.update_parent(
            parent_id=test_parent_orm.id,
            update_data=update_data,
            current_user=test_teacher_orm
        )

        assert updated_parent.email == "new.parent.email@example.com"
        assert updated_parent.timezone == "Europe/London"

        # Verify in DB
        db_user = await user_service.get_user_by_id(test_parent_orm.id)
        assert db_user.email == "new.parent.email@example.com"
        assert db_user.timezone == "Europe/London"

    async def test_update_parent_password_change(
        self,
        parents_service: ParentService,
        test_parent_orm: db_models.Parents,
        user_service: UserService
    ):
        """Tests that a parent can update their own password."""
        print("\n--- Testing update_parent password change ---")
        new_password = "new_secure_password_456"
        update_data = user_models.ParentUpdate(password=new_password)

        original_hash = test_parent_orm.password
        
        await parents_service.update_parent(
            parent_id=test_parent_orm.id,
            update_data=update_data,
            current_user=test_parent_orm
        )

        db_user = await user_service.get_user_by_id(test_parent_orm.id)
        assert db_user.password != original_hash
        assert HashedPassword.verify(new_password, db_user.password)

    async def test_update_parent_as_unrelated_parent_forbidden(
        self,
        parents_service: ParentService,
        test_parent_orm: db_models.Parents,
        test_unrelated_parent_orm: db_models.Parents
    ):
        """Tests that an unrelated parent is forbidden from updating a profile."""
        update_data = user_models.ParentUpdate(first_name="Forbidden")
        
        with pytest.raises(HTTPException) as e:
            await parents_service.update_parent(
                parent_id=test_parent_orm.id,
                update_data=update_data,
                current_user=test_unrelated_parent_orm
            )
        assert e.value.status_code == 403

    async def test_update_parent_not_found(
        self,
        parents_service: ParentService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that updating a non-existent parent raises a 404."""
        update_data = user_models.ParentUpdate(first_name="NotFound")

        with pytest.raises(HTTPException) as e:
            await parents_service.update_parent(
                parent_id=UUID(int=0),
                update_data=update_data,
                current_user=test_teacher_orm
            )
        assert e.value.status_code == 404

    # --- Tests for delete_parent ---

    async def test_delete_parent_as_teacher(
        self,
        parents_service: ParentService,
        test_teacher_orm: db_models.Teachers,
        user_service: UserService
    ):
        """Tests that a teacher can successfully delete a parent without students."""
        print("\n--- Testing delete_parent as teacher ---")
        # ARRANGE: Create a new parent with no students to delete
        parent_to_delete_data = user_models.ParentCreate(
            email="delete.me.teacher@example.com",
            password="password123",
            first_name="Delete",
            last_name="Me",
        )
        created_parent = await parents_service.create_parent(parent_to_delete_data, "1.1.1.1")
        await parents_service.db.commit()

        # ACT
        success = await parents_service.delete_parent(created_parent.id, test_teacher_orm)
        assert success is True
        await parents_service.db.commit()

        # ASSERT
        deleted_user = await user_service.get_user_by_id(created_parent.id)
        assert deleted_user is None

    async def test_delete_parent_as_self(
        self,
        parents_service: ParentService,
        user_service: UserService
    ):
        """Tests that a parent can successfully delete their own profile if they have no students."""
        print("\n--- Testing delete_parent as self ---")
        # ARRANGE
        parent_to_delete_data = user_models.ParentCreate(
            email="delete.me.self@example.com",
            password="password123",
            first_name="Delete",
            last_name="Myself",
        )
        created_parent_read = await parents_service.create_parent(parent_to_delete_data, "2.2.2.2")
        await parents_service.db.commit()
        
        # Fetch the ORM object to use as the 'current_user'
        parent_orm = await user_service.get_user_by_id(created_parent_read.id)

        # ACT
        success = await parents_service.delete_parent(parent_orm.id, parent_orm)
        assert success is True
        await parents_service.db.commit()

        # ASSERT
        deleted_user = await user_service.get_user_by_id(parent_orm.id)
        assert deleted_user is None

    async def test_delete_parent_with_associated_students_fails(
        self,
        parents_service: ParentService,
        test_parent_orm: db_models.Parents, # This parent has students
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that deleting a parent with associated students raises a 400 error."""
        print("\n--- Testing delete_parent with students fails ---")
        with pytest.raises(HTTPException) as e:
            await parents_service.delete_parent(test_parent_orm.id, test_teacher_orm)
        
        assert e.value.status_code == 400
        assert "Cannot delete a parent with associated students" in e.value.detail

    async def test_delete_parent_as_unrelated_parent_forbidden(
        self,
        parents_service: ParentService,
        test_parent_orm: db_models.Parents,
        test_unrelated_parent_orm: db_models.Parents
    ):
        """Tests that an unrelated parent is forbidden from deleting a profile."""
        with pytest.raises(HTTPException) as e:
            await parents_service.delete_parent(test_parent_orm.id, test_unrelated_parent_orm)
        assert e.value.status_code == 403

    async def test_delete_parent_not_found(
        self,
        parents_service: ParentService,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that deleting a non-existent parent raises a 404."""
        with pytest.raises(HTTPException) as e:
            await parents_service.delete_parent(UUID(int=0), test_teacher_orm)
        assert e.value.status_code == 404




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
        print("--- Successfully created student (API model) ---")
        pprint(new_student.model_dump())

    async def test_create_student_as_parent_mismatched_parent_id(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Parent cannot create a student for a parent_id that does not match their own."""
        print("\n--- Testing create_student as PARENT (Mismatched Parent ID) ---")

        # Set parent_id to a different parent (e.g., TEST_TEACHER_ID, which is not a parent)
        # or a random UUID that doesn't match test_parent_orm.id
        valid_student_data["parent_id"] = TEST_TEACHER_ID # This is guaranteed to be a different ID
        valid_student_data["email"] = "mismatched.parent@example.com" # different email to avoid conflict
        create_model = user_models.StudentCreate(**valid_student_data)

        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_parent_orm)

        assert e.value.status_code == 403
        assert "Parents can only create students for themselves." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

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

    # --- Tests for update_student ---

    async def test_update_student_as_teacher(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that a Teacher can successfully update a student's fields."""
        print("\n--- Testing update_student as TEACHER ---")
        
        update_payload = user_models.StudentUpdate(
            first_name="UpdatedByTeacher",
            grade=11
        )
        
        updated_student = await student_service.update_student(
            student_id=test_student_orm.id,
            update_data=update_payload,
            current_user=test_teacher_orm
        )
        
        assert isinstance(updated_student, user_models.StudentRead)
        assert updated_student.id == test_student_orm.id
        assert updated_student.first_name == "UpdatedByTeacher"
        assert updated_student.grade == 11
        # Ensure other fields are unchanged
        assert updated_student.last_name == test_student_orm.last_name
        
        print("--- Successfully updated student (API model) ---")
        pprint(updated_student.model_dump())

    async def test_update_student_as_parent(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that a Parent can successfully update their own child."""
        print("\n--- Testing update_student as PARENT ---")
        
        # Pre-condition check
        assert test_student_orm.parent_id == test_parent_orm.id

        update_payload = user_models.StudentUpdate(
            cost=Decimal("99.99")
        )
        
        updated_student = await student_service.update_student(
            student_id=test_student_orm.id,
            update_data=update_payload,
            current_user=test_parent_orm
        )
        
        assert isinstance(updated_student, user_models.StudentRead)
        assert updated_student.cost == Decimal("99.99")
        
        print("--- Successfully updated student (API model) ---")
        pprint(updated_student.model_dump())

    async def test_update_student_as_unrelated_parent_forbidden(
        self,
        student_service: StudentService,
        test_unrelated_parent_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that an unrelated Parent is FORBIDDEN from updating a student."""
        print("\n--- Testing update_student as UNRELATED PARENT (Forbidden) ---")
        
        update_payload = user_models.StudentUpdate(first_name="ForbiddenUpdate")
        
        with pytest.raises(HTTPException) as e:
            await student_service.update_student(
                student_id=test_student_orm.id,
                update_data=update_payload,
                current_user=test_unrelated_parent_orm
            )
        
        assert e.value.status_code == 403
        assert "only update their own children" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_student_as_student_forbidden(
        self,
        student_service: StudentService,
        test_student_orm: db_models.Students
    ):
        """Tests that a Student is FORBIDDEN from updating their own profile."""
        print("\n--- Testing update_student as STUDENT (Forbidden) ---")
        
        update_payload = user_models.StudentUpdate(first_name="ForbiddenUpdate")
        
        with pytest.raises(HTTPException) as e:
            await student_service.update_student(
                student_id=test_student_orm.id,
                update_data=update_payload,
                current_user=test_student_orm
            )
        
        assert e.value.status_code == 403
        assert "permission to update students" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_student_replace_nested_lists(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that updating nested lists (subjects, availability) replaces them entirely."""
        print("\n--- Testing update_student replaces nested lists ---")
        
        # 1. ARRANGE: Fetch a fresh, fully-loaded student object to avoid lazy-loading issues
        student_id_to_update = test_student_orm.id
        student_to_update = await student_service.get_user_by_id(student_id_to_update)
        assert student_to_update is not None

        # Pre-condition: Ensure the student has existing subjects/availability
        assert len(student_to_update.student_subjects) > 0
        assert len(student_to_update.student_availability_intervals) > 0

        new_subjects = [
            user_models.StudentSubjectWrite(subject=SubjectEnum.CHEMISTRY, lessons_per_week=3)
        ]
        new_availability = [
            user_models.StudentAvailabilityIntervalWrite(day_of_week=7, start_time=time(10,0), end_time=time(12,0), availability_type="sleep")
        ]
        
        update_payload = user_models.StudentUpdate(
            student_subjects=new_subjects,
            student_availability_intervals=new_availability
        )
        
        # 2. ACT
        updated_student = await student_service.update_student(
            student_id=student_id_to_update,
            update_data=update_payload,
            current_user=test_teacher_orm
        )
        
        # 3. ASSERT
        assert len(updated_student.student_subjects) == 1
        assert updated_student.student_subjects[0].subject == SubjectEnum.CHEMISTRY
        assert updated_student.student_subjects[0].lessons_per_week == 3
        
        assert len(updated_student.student_availability_intervals) == 1
        assert updated_student.student_availability_intervals[0].day_of_week == 7
        assert updated_student.student_availability_intervals[0].availability_type == "sleep"
        
        print("--- Successfully replaced nested lists ---")
        pprint(updated_student.model_dump())

    async def test_update_student_not_found(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that updating a non-existent student raises a 404."""
        print("\n--- Testing update_student for non-existent ID ---")
        
        update_payload = user_models.StudentUpdate(first_name="NotFound")
        
        with pytest.raises(HTTPException) as e:
            await student_service.update_student(
                student_id=UUID(int=0),
                update_data=update_payload,
                current_user=test_teacher_orm
            )
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    # --- Tests for delete_student ---

    async def test_delete_student_as_parent(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Parent can delete their own child."""
        print("\n--- Testing delete_student as PARENT ---")
        
        # 1. Create a new student to delete
        valid_student_data["email"] = "to.be.deleted.by.parent@example.com"
        valid_student_data["parent_id"] = test_parent_orm.id
        create_model = user_models.StudentCreate(**valid_student_data)
        student_to_delete = await student_service.create_student(create_model, test_parent_orm)
        
        # 2. Act: Delete the student
        success = await student_service.delete_student(student_to_delete.id, test_parent_orm)
        assert success is True
        await student_service.db.commit() # Commit the deletion
        
        # 3. Verify: The student should now be gone
        deleted_user = await student_service.get_user_by_id(student_to_delete.id)
        assert deleted_user is None
        print(f"--- Successfully deleted student {student_to_delete.id} ---")

    async def test_delete_student_as_teacher(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Teacher can delete a student."""
        print("\n--- Testing delete_student as TEACHER ---")
        
        # 1. Create a new student to delete
        valid_student_data["email"] = "to.be.deleted.by.teacher@example.com"
        create_model = user_models.StudentCreate(**valid_student_data)
        student_to_delete = await student_service.create_student(create_model, test_teacher_orm)
        
        # 2. Act: Delete the student
        success = await student_service.delete_student(student_to_delete.id, test_teacher_orm)
        assert success is True
        await student_service.db.commit() # Commit the deletion
        
        # 3. Verify: The student should now be gone
        deleted_user = await student_service.get_user_by_id(student_to_delete.id)
        assert deleted_user is None
        print(f"--- Successfully deleted student {student_to_delete.id} ---")

    async def test_delete_student_as_unrelated_parent_forbidden(
        self,
        student_service: StudentService,
        test_unrelated_parent_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that an unrelated Parent is FORBIDDEN from deleting a student."""
        print("\n--- Testing delete_student as UNRELATED PARENT (Forbidden) ---")
        
        with pytest.raises(HTTPException) as e:
            await student_service.delete_student(test_student_orm.id, test_unrelated_parent_orm)
            
        assert e.value.status_code == 403
        assert "only delete their own children" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_delete_student_as_student_forbidden(
        self,
        student_service: StudentService,
        test_student_orm: db_models.Students
    ):
        """Tests that a Student is FORBIDDEN from deleting themselves."""
        print("\n--- Testing delete_student as STUDENT (Forbidden) ---")
        
        with pytest.raises(HTTPException) as e:
            await student_service.delete_student(test_student_orm.id, test_student_orm)
            
        assert e.value.status_code == 403
        assert "permission to delete students" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_delete_student_not_found(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that deleting a non-existent student raises a 404."""
        print("\n--- Testing delete_student for non-existent ID ---")
        
        with pytest.raises(HTTPException) as e:
            await student_service.delete_student(UUID(int=0), test_teacher_orm)
            
        assert e.value.status_code == 404
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")


