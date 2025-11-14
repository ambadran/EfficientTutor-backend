import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock
import copy

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.main import app
from src.efficient_tutor_backend.services.tuition_service import TuitionService

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestStudentAPIPOST:
    """Test class for POST endpoints of the Students API."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Fixture to mock and restore dependencies for each test."""
        # Mock TuitionService before each test
        mock_tuition_service = MagicMock(spec=TuitionService)
        mock_tuition_service.regenerate_all_tuitions = AsyncMock()
        app.dependency_overrides[TuitionService] = lambda: mock_tuition_service
        
        self.mock_tuition_service = mock_tuition_service
        
        yield
        
        # Restore original dependencies after each test
        app.dependency_overrides = {}

    async def test_create_student_as_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents,
        valid_student_data: dict
    ):
        """Test a teacher successfully creating a new student."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        # Use a copy of the valid data and ensure parent_id is correct
        student_payload = copy.deepcopy(valid_student_data)
        student_payload["parent_id"] = str(test_parent_orm.id)
        student_payload["email"] = f"teacher.created.{uuid4()}@example.com"

        print(f"Attempting to create student as teacher: {student_payload['email']}")
        response = client.post("/students/", headers=headers, json=student_payload)

        assert response.status_code == 201, response.json()
        created_student = user_models.StudentRead(**response.json())
        
        assert created_student.email == student_payload["email"]
        assert created_student.parent_id == test_parent_orm.id
        assert created_student.student_subjects[0].subject.value == student_payload["student_subjects"][0]["subject"]
        
        # Verify that the mocked service method was called
        self.mock_tuition_service.regenerate_all_tuitions.assert_awaited_once()
        print("Successfully created student as teacher.")

    async def test_create_student_as_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        valid_student_data: dict
    ):
        """Test a parent successfully creating a new student for themselves."""
        headers = auth_headers_for_user(test_parent_orm)
        
        student_payload = copy.deepcopy(valid_student_data)
        student_payload["parent_id"] = str(test_parent_orm.id) # Parent can only create for self
        student_payload["email"] = f"parent.created.{uuid4()}@example.com"

        print(f"Attempting to create student as parent: {student_payload['email']}")
        response = client.post("/students/", headers=headers, json=student_payload)

        assert response.status_code == 201, response.json()
        created_student = user_models.StudentRead(**response.json())
        
        assert created_student.email == student_payload["email"]
        assert created_student.parent_id == test_parent_orm.id
        
        self.mock_tuition_service.regenerate_all_tuitions.assert_awaited_once()
        print("Successfully created student as parent.")

    async def test_create_student_as_parent_for_other_parent_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_unrelated_parent_orm: db_models.Parents,
        valid_student_data: dict
    ):
        """Test a parent is forbidden from creating a student for another parent."""
        # Authenticate as the unrelated parent
        headers = auth_headers_for_user(test_unrelated_parent_orm)
        
        student_payload = copy.deepcopy(valid_student_data)
        # Try to assign the student to the other parent
        student_payload["parent_id"] = str(test_parent_orm.id)
        student_payload["email"] = f"forbidden.student.{uuid4()}@example.com"

        print(f"Attempting to create student for another parent (should be forbidden).")
        response = client.post("/students/", headers=headers, json=student_payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "Parents can only create students for themselves."
        
        # Ensure the regeneration method was NOT called
        self.mock_tuition_service.regenerate_all_tuitions.assert_not_awaited()
        print("Correctly forbidden from creating student for another parent.")

    async def test_create_student_with_existing_email_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students,
        valid_student_data: dict
    ):
        """Test that creating a student with an existing email fails."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        student_payload = copy.deepcopy(valid_student_data)
        student_payload["email"] = test_student_orm.email # Use existing email

        print(f"Attempting to create student with existing email: {student_payload['email']}")
        response = client.post("/students/", headers=headers, json=student_payload)

        assert response.status_code == 400
        assert response.json()["detail"] == "Email already registered."
        self.mock_tuition_service.regenerate_all_tuitions.assert_not_awaited()
        print("Correctly failed to create student with duplicate email.")
