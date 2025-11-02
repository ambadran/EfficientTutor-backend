'''

'''
import pytest
from uuid import UUID
from fastapi import HTTPException

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import (
    UserService, 
    ParentService, 
    StudentService
)
from tests.constants import TEST_TEACHER_ID, TEST_PARENT_ID

from pprint import pp as pprint

# --- Test Classes ---

@pytest.mark.anyio
class TestUserService:
    
    # We now request 'test_teacher_orm' instead of 'test_teacher'
    async def test_get_user_by_id(
        self, 
        user_service: UserService, 
        test_teacher_orm: db_models.Users  # <-- Use the new fixture
    ):
        """Tests fetching a user by their ID."""
        user = await user_service.get_user_by_id(test_teacher_orm.id)

        pprint(user.__dict__)
        
        assert user is not None
        assert user.id == test_teacher_orm.id
        assert user.email == test_teacher_orm.email

    async def test_get_user_by_id_not_found(self, user_service: UserService):
        """Tests that None is returned for a non-existent ID."""
        user = await user_service.get_user_by_id(UUID(int=0)) # Random UUID
        assert user is None

    async def test_get_full_user_by_email(
        self, 
        user_service: UserService, 
        test_teacher_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests fetching a user by their email."""
        user = await user_service.get_full_user_by_email(test_teacher_orm.email)

        pprint(user.__dict__)
        
        assert user is not None
        assert user.id == test_teacher_orm.id

    async def test_get_users_by_ids(
        self, 
        user_service: UserService, 
        test_teacher_orm: db_models.Users,
        test_parent_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests fetching a list of users by their IDs."""
        user_ids = [test_teacher_orm.id, test_parent_orm.id]
        users = await user_service.get_users_by_ids(user_ids)

        print("One of the users full data:")
        pprint(users[0].__dict__)

        assert len(users) == 2
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
        
        assert len(students) >= 1
        assert any(s.id == test_student_orm.id for s in students)

    async def test_get_all_as_parent(
        self, 
        student_service: StudentService, 
        test_parent_orm: db_models.Users, # <-- Use the new fixture
        test_student_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests that a PARENT can get all students."""
        students = await student_service.get_all(current_user=test_parent_orm)
        
        assert len(students) >= 1
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
