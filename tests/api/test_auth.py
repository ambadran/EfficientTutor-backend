import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock
from sqlalchemy import select

from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database import models as db_models
from tests.constants import (
        TEST_PASSWORD_ADMIN,
        TEST_PASSWORD_TEACHER,
        TEST_PASSWORD_PARENT,
        TEST_PASSWORD_STUDENT
        )

# Note: No hardcoded emails. We use the emails from the fixtures.

@pytest.mark.anyio
class TestAuthAPI:
    """
    Tests for the authentication API endpoints (/auth).
    - Login tests USE EXISTING fixtures from conftest.py.
    - Signup tests CREATE new data to test the creation process.
    """

    # --- Login Tests ---

    async def test_login_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """
        Test successful login for a parent user using the test_parent_orm fixture.
        """
        print(f"Attempting login for parent: {test_parent_orm.email}")
        response = client.post(
            "/auth/login",
            data={"username": test_parent_orm.email, "password": TEST_PASSWORD_PARENT}
        )

        assert response.status_code == 200, response.json()
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        print("Parent login successful.")

    async def test_login_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Test successful login for a teacher user using the test_teacher_orm fixture.
        """
        print(f"Attempting login for teacher: {test_teacher_orm.email}")
        response = client.post(
            "/auth/login",
            data={"username": test_teacher_orm.email, "password": TEST_PASSWORD_TEACHER}
        )

        assert response.status_code == 200, response.json()
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        print("Teacher login successful.")

    async def test_login_admin_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """
        Test successful login for an admin user using the test_admin_orm fixture.
        """
        print(f"Attempting login for admin: {test_admin_orm.email}")
        response = client.post(
            "/auth/login",
            data={"username": test_admin_orm.email, "password": TEST_PASSWORD_ADMIN}
        )

        assert response.status_code == 200, response.json()
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        print("Admin login successful.")

    async def test_login_student_success(
        self, 
        client: TestClient, 
        test_student_orm: db_models.Students
    ):
        """
        Test successful login for an student user using the test_student_orm fixture.
        """
        print(f"Attempting login for student: {test_student_orm.email}")
        response = client.post(
            "/auth/login",
            data={"username": test_student_orm.email, "password": TEST_PASSWORD_STUDENT}
        )

        assert response.status_code == 200, response.json()
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        print("Student login successful.")

    async def test_login_invalid_password(
        self, client: TestClient, test_parent_orm: db_models.Parents
    ):
        """
        Test login with an invalid password.
        """
        print(f"Attempting login for {test_parent_orm.email} with wrong password.")
        response = client.post(
            "/auth/login",
            data={"username": test_parent_orm.email, "password": "wrongpassword"}
        )

        assert response.status_code == 401
        # Per protocol, read the exact error message from the source code.
        # auth_service.py raises "Incorrect email or password".
        assert response.json()["detail"] == "Incorrect email or password"
        print("Login with invalid password failed as expected.")

    async def test_login_non_existent_user(self, client: TestClient):
        """
        Test login with a non-existent user email.
        """
        print("Attempting login for a non-existent user.")
        response = client.post(
            "/auth/login",
            data={"username": "nonexistent@example.com", "password": "anypassword"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"
        print("Login for non-existent user failed as expected.")

    # --- Signup Tests ---

    async def test_signup_parent_success(
        self, 
        client: TestClient, 
        db_session: AsyncSession, 
        mock_geo_service: MagicMock
    ):
        """
        Test successful parent signup. This test correctly creates a new user.
        """
        new_parent_email = "new.parent.signup@example.com"
        
        # Verify user does NOT exist before signup
        existing_user = await db_session.scalar(select(db_models.Users).filter_by(email=new_parent_email))
        assert existing_user is None

        parent_data = user_models.ParentCreate(
            email=new_parent_email,
            password='new_parent_pass',
            first_name="New",
            last_name="Parent",
        )

        print(f"Attempting to sign up new parent: {new_parent_email}")
        response = client.post(
            "/auth/signup/parent",
            json=parent_data.model_dump()
        )

        assert response.status_code == 201, response.json()
        parent_read = user_models.ParentRead(**response.json())
        assert parent_read.email == new_parent_email
        assert parent_read.first_name == "New"
        # Check values from mock_geo_service
        assert parent_read.timezone == "America/New_York"
        assert parent_read.currency == "USD"
        print("Parent signup successful.")

        # Verify user was flushed to the DB (it will be rolled back by the fixture)
        await db_session.flush()
        db_parent = await db_session.get(db_models.Parents, parent_read.id)
        assert db_parent is not None
        assert db_parent.id == parent_read.id
        print("Verified new parent exists in DB session before rollback.")

    async def test_signup_parent_existing_email(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """
        Test parent signup with an email that already exists from a fixture.
        """
        parent_data = user_models.ParentCreate(
            email=test_parent_orm.email, # Existing email
            password='duplicate_parent_pass',
            first_name="Duplicate",
            last_name="Parent",
        )

        print(f"Attempting to sign up with existing email: {test_parent_orm.email}")
        response = client.post(
            "/auth/signup/parent",
            json=parent_data.model_dump()
        )

        assert response.status_code == 400 # user_service.py raises 400
        # Per protocol, read the exact error message from the source code.
        # user_service.py raises "Email already registered."
        assert response.json()["detail"] == "Email already registered."
        print("Signup with existing email failed as expected.")

    async def test_signup_teacher_success(
        self,
        client: TestClient, 
        db_session: AsyncSession,
        mock_geo_service: MagicMock
    ):
        """
        Test successful teacher signup. This test correctly creates a new user.
        """
        new_teacher_email = "new.teacher.signup@example.com"

        # Verify user does NOT exist before signup
        existing_user = await db_session.scalar(select(db_models.Users).filter_by(email=new_teacher_email))
        assert existing_user is None

        teacher_data = user_models.TeacherCreate(
            email=new_teacher_email,
            password='teacher_pass',
            first_name="New",
            last_name="Teacher",
        )

        print(f"Attempting to sign up new teacher: {new_teacher_email}")
        response = client.post(
            "/auth/signup/teacher",
            json=teacher_data.model_dump()
        )

        assert response.status_code == 201, response.json()
        teacher_read = user_models.TeacherRead(**response.json())
        assert teacher_read.email == new_teacher_email
        assert teacher_read.first_name == "New"
        # Check values from mock_geo_service
        assert teacher_read.timezone == "America/New_York"
        assert teacher_read.currency == "USD"
        print("Teacher signup successful.")

        # Verify user was flushed to the DB (it will be rolled back by the fixture)
        await db_session.flush()
        db_teacher = await db_session.get(db_models.Teachers, teacher_read.id)
        assert db_teacher is not None
        assert db_teacher.id == teacher_read.id
        print("Verified new teacher exists in DB session before rollback.")

    async def test_signup_teacher_existing_email(
        self,
        client: TestClient, 
        test_teacher_orm: db_models.Teachers
    ):
        """
        Test teacher signup with an email that already exists from a fixture.
        """
        teacher_data = user_models.TeacherCreate(
            email=test_teacher_orm.email, # Existing email
            password='teacher_pass',
            first_name="Duplicate",
            last_name="Teacher",
        )

        print(f"Attempting to sign up with existing email: {test_teacher_orm.email}")
        response = client.post(
            "/auth/signup/teacher",
            json=teacher_data.model_dump()
        )

        assert response.status_code == 400 # user_service.py raises 400
        assert response.json()["detail"] == "Email already registered."
        print("Signup with existing email failed as expected.")
