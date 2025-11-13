import pytest
from uuid import UUID
from fastapi import HTTPException
from datetime import time
from decimal import Decimal
from unittest.mock import MagicMock

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import UserService, ParentService, StudentService
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import UserRole
from src.efficient_tutor_backend.common.security_utils import HashedPassword

from pprint import pp as pprint


@pytest.mark.anyio
class TestParentService:

    # --- Tests for get_all ---

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

    # --- Tests for create_parent ---

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



