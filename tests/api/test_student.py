import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import copy

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import user as user_models

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestStudentAPIGET:
    """Test class for GET endpoints of the Students API."""

    async def test_get_student_by_id_success(
        self,
        client: TestClient,
        test_student_orm: db_models.Students
    ):
        """Test successfully fetching a student by their ID."""
        student_id = test_student_orm.id
        print(f"Attempting to fetch student with ID: {student_id}")

        response = client.get(f"/students/{student_id}")

        assert response.status_code == 200, response.json()
        student_data = user_models.StudentRead(**response.json())
        
        assert student_data.id == student_id
        assert student_data.email == test_student_orm.email
        print(f"Successfully fetched student {student_id}")

    async def test_get_student_by_id_not_found(
        self,
        client: TestClient
    ):
        """Test fetching a student with an ID that does not exist."""
        non_existent_id = uuid4()
        print(f"Attempting to fetch non-existent student with ID: {non_existent_id}")

        response = client.get(f"/students/{non_existent_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"
        print("Fetching non-existent student failed as expected.")

    async def test_get_all_students_as_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_student_orm: db_models.Students
    ):
        """Test a parent successfully fetching their own list of students (children)."""
        headers = auth_headers_for_user(test_parent_orm)
        print(f"Parent {test_parent_orm.email} fetching their students.")
        
        response = client.get("/students/", headers=headers)
        assert response.status_code == 200, response.json()
        
        response_data = response.json()
        assert isinstance(response_data, list)
        # The test parent should have one student from the seed data
        assert len(response_data) > 0
        student_ids = [student['id'] for student in response_data]
        assert str(test_student_orm.id) in student_ids
        print("Parent successfully fetched their list of children.")

    async def test_get_all_students_as_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test a teacher successfully fetching the list of students they teach."""
        headers = auth_headers_for_user(test_teacher_orm)
        print(f"Teacher {test_teacher_orm.email} fetching their students.")

        response = client.get("/students/", headers=headers)
        assert response.status_code == 200, response.json()
        
        response_data = response.json()
        assert isinstance(response_data, list)
        print("Teacher successfully fetched their list of students.")

    async def test_get_all_students_as_admin_forbidden(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test that an admin is forbidden from fetching the student list."""
        headers = auth_headers_for_user(test_admin_orm)
        print(f"Admin {test_admin_orm.email} attempting to fetch students.")

        response = client.get("/students/", headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "User with role 'admin' is not authorized to list students."
        print("Admin was correctly forbidden from fetching students.")


@pytest.mark.anyio
class TestStudentAPIPOST:
    """Test class for POST endpoints of the Students API."""

    async def test_create_student_as_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        valid_student_data: dict
    ):
        """Test a teacher successfully creating a new student."""
        headers = auth_headers_for_user(test_teacher_orm)
        payload = valid_student_data
        
        print(f"Teacher {test_teacher_orm.email} creating student {payload['email']}.")
        response = client.post("/students/", headers=headers, json=payload)

        assert response.status_code == 201, response.json()
        created_student = user_models.StudentRead(**response.json())
        assert created_student.email == payload["email"]
        assert str(created_student.parent_id) == payload["parent_id"]
        print("Teacher successfully created student.")

    async def test_create_student_as_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        valid_student_data: dict
    ):
        """Test a parent successfully creating a new student for themselves."""
        headers = auth_headers_for_user(test_parent_orm)
        payload = copy.deepcopy(valid_student_data)
        payload["parent_id"] = str(test_parent_orm.id) # Parent can only create for self
        
        print(f"Parent {test_parent_orm.email} creating student for themselves.")
        response = client.post("/students/", headers=headers, json=payload)

        assert response.status_code == 201, response.json()
        created_student = user_models.StudentRead(**response.json())
        assert created_student.email == payload["email"]
        assert created_student.parent_id == test_parent_orm.id
        print("Parent successfully created their own child.")

    async def test_create_student_as_parent_for_other_parent_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_unrelated_parent_orm: db_models.Parents,
        valid_student_data: dict
    ):
        """Test a parent is forbidden from creating a student for another parent."""
        headers = auth_headers_for_user(test_parent_orm)
        payload = copy.deepcopy(valid_student_data)
        payload["parent_id"] = str(test_unrelated_parent_orm.id) # Set to other parent

        print(f"Parent {test_parent_orm.email} attempting to create student for other parent.")
        response = client.post("/students/", headers=headers, json=payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "Parents can only create students for themselves."
        print("Parent was correctly forbidden from creating student for another parent.")

    async def test_create_student_with_invalid_teacher_id_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        valid_student_data: dict
    ):
        """Test creating a student fails if a teacher_id in subjects is invalid."""
        headers = auth_headers_for_user(test_teacher_orm)
        payload = copy.deepcopy(valid_student_data)
        invalid_teacher_id = uuid4()
        payload["student_subjects"][0]["teacher_id"] = str(invalid_teacher_id)

        print(f"Attempting to create student with invalid teacher ID {invalid_teacher_id}.")
        response = client.post("/students/", headers=headers, json=payload)

        assert response.status_code == 404
        assert f"Invalid teacher_id(s) provided: {invalid_teacher_id}" in response.json()["detail"]
        print("Student creation failed with invalid teacher ID as expected.")


@pytest.mark.anyio
class TestStudentAPIPATCH:
    """Test class for PATCH endpoints of the Students API."""

    async def test_update_student_by_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students
    ):
        """Test a teacher successfully updating a student's profile."""
        headers = auth_headers_for_user(test_teacher_orm)
        student_id = test_student_orm.id
        payload = {"first_name": "TeacherWasHere"}

        print(f"Teacher {test_teacher_orm.email} updating student {student_id}.")
        response = client.patch(f"/students/{student_id}", headers=headers, json=payload)

        assert response.status_code == 200, response.json()
        updated_student = user_models.StudentRead(**response.json())
        assert updated_student.first_name == "TeacherWasHere"
        print("Teacher successfully updated student.")

    async def test_update_student_by_own_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_student_orm: db_models.Students
    ):
        """Test a parent successfully updating their own child's profile."""
        headers = auth_headers_for_user(test_parent_orm)
        student_id = test_student_orm.id
        payload = {"last_name": "ParentWasHere"}

        print(f"Parent {test_parent_orm.email} updating their child {student_id}.")
        response = client.patch(f"/students/{student_id}", headers=headers, json=payload)

        assert response.status_code == 200, response.json()
        updated_student = user_models.StudentRead(**response.json())
        assert updated_student.last_name == "ParentWasHere"
        print("Parent successfully updated their child.")

    async def test_update_student_by_unrelated_parent_forbidden(
        self,
        client: TestClient,
        test_unrelated_parent_orm: db_models.Parents,
        test_student_orm: db_models.Students
    ):
        """Test an unrelated parent is forbidden from updating a student."""
        headers = auth_headers_for_user(test_unrelated_parent_orm)
        student_id = test_student_orm.id
        payload = {"first_name": "ForbiddenUpdate"}

        print(f"Unrelated parent {test_unrelated_parent_orm.email} attempting to update student {student_id}.")
        response = client.patch(f"/students/{student_id}", headers=headers, json=payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "Parents can only update their own children."
        print("Unrelated parent was correctly forbidden from updating student.")

    async def test_update_student_by_admin_forbidden(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins,
        test_student_orm: db_models.Students
    ):
        """Test an admin is forbidden from updating a student."""
        headers = auth_headers_for_user(test_admin_orm)
        student_id = test_student_orm.id
        payload = {"first_name": "AdminUpdate"}

        print(f"Admin {test_admin_orm.email} attempting to update student {student_id}.")
        response = client.patch(f"/students/{student_id}", headers=headers, json=payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to update students."
        print("Admin was correctly forbidden from updating student.")


@pytest.mark.anyio
class TestStudentAPIDELETE:
    """Test class for DELETE endpoints of the Students API."""

    async def test_delete_student_by_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students
    ):
        """Test a teacher successfully deleting a student."""
        headers = auth_headers_for_user(test_teacher_orm)
        student_id = test_student_orm.id

        print(f"Teacher {test_teacher_orm.email} deleting student {student_id}.")
        response = client.delete(f"/students/{student_id}", headers=headers)

        assert response.status_code == 204
        print("Teacher successfully deleted student.")

    async def test_delete_student_by_own_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_student_orm: db_models.Students
    ):
        """Test a parent successfully deleting their own child."""
        headers = auth_headers_for_user(test_parent_orm)
        student_id = test_student_orm.id

        print(f"Parent {test_parent_orm.email} deleting their child {student_id}.")
        response = client.delete(f"/students/{student_id}", headers=headers)

        assert response.status_code == 204
        print("Parent successfully deleted their child.")

    async def test_delete_student_by_unrelated_parent_forbidden(
        self,
        client: TestClient,
        test_unrelated_parent_orm: db_models.Parents,
        test_student_orm: db_models.Students
    ):
        """Test an unrelated parent is forbidden from deleting a student."""
        headers = auth_headers_for_user(test_unrelated_parent_orm)
        student_id = test_student_orm.id

        print(f"Unrelated parent {test_unrelated_parent_orm.email} attempting to delete student {student_id}.")
        response = client.delete(f"/students/{student_id}", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "Parents can only delete their own children."
        print("Unrelated parent was correctly forbidden from deleting student.")

    async def test_delete_student_by_admin_forbidden(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins,
        test_student_orm: db_models.Students
    ):
        """Test an admin is forbidden from deleting a student."""
        headers = auth_headers_for_user(test_admin_orm)
        student_id = test_student_orm.id

        print(f"Admin {test_admin_orm.email} attempting to delete student {student_id}.")
        response = client.delete(f"/students/{student_id}", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to delete students."
        print("Admin was correctly forbidden from deleting student.")
