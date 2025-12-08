import pytest
from uuid import UUID
from fastapi import HTTPException
from datetime import time
from decimal import Decimal

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import UserService
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, UserRole
from unittest.mock import MagicMock

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
        pprint(user.teacher_specialties)
        
        assert user is not None
        assert user.id == test_teacher_orm.id
        assert user.email == test_teacher_orm.email
        assert user.teacher_specialties is not None
        assert isinstance(user.teacher_specialties, list)
        assert len(user.teacher_specialties) > 0
        assert isinstance(user.teacher_specialties[0], db_models.TeacherSpecialties)

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
        pprint(user.availability_intervals[0].__dict__)
        
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
        pprint(user.teacher_specialties)
        
        assert user is not None
        assert user.id == test_teacher_orm.id
        assert user.email == test_teacher_orm.email
        assert user.teacher_specialties is not None
        assert isinstance(user.teacher_specialties, list)
        assert len(user.teacher_specialties) > 0
        assert isinstance(user.teacher_specialties[0], db_models.TeacherSpecialties)

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
        pprint(user.availability_intervals[0].__dict__)
 
        
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


