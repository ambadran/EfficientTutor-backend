import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import user as user_models

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestTeacherAPIGET:
    """Test class for GET endpoints of the Teachers API."""

    async def test_get_teacher_by_id_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test successfully fetching a teacher by their ID."""
        teacher_id = test_teacher_orm.id
        print(f"Attempting to fetch teacher with ID: {teacher_id}")

        response = client.get(f"/teachers/{teacher_id}")

        assert response.status_code == 200, response.json()
        teacher_data = user_models.TeacherRead(**response.json())
        
        assert teacher_data.id == teacher_id
        assert teacher_data.email == test_teacher_orm.email
        print(f"Successfully fetched teacher {teacher_id}")

    async def test_get_teacher_by_id_not_found(
        self,
        client: TestClient
    ):
        """Test fetching a teacher with an ID that does not exist."""
        non_existent_id = uuid4()
        print(f"Attempting to fetch non-existent teacher with ID: {non_existent_id}")

        response = client.get(f"/teachers/{non_existent_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Teacher not found"
        print("Fetching non-existent teacher failed as expected.")

    async def test_get_all_teachers_as_admin_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test that an admin can successfully fetch the list of all teachers."""
        print(f"Attempting to fetch all teachers as admin: {test_admin_orm.email}")
        headers = auth_headers_for_user(test_admin_orm)
        
        response = client.get("/teachers/", headers=headers)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        print("Successfully fetched teachers list as an admin.")

    async def test_get_all_teachers_as_teacher_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test that a teacher is forbidden from fetching the list of all teachers."""
        print(f"Attempting to fetch all teachers as teacher: {test_teacher_orm.email}")
        headers = auth_headers_for_user(test_teacher_orm)

        response = client.get("/teachers/", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view this list."
        print("Teacher was correctly forbidden from fetching all teachers.")

    async def test_get_all_teachers_as_parent_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test that a parent is forbidden from fetching the list of all teachers."""
        print(f"Attempting to fetch all teachers as parent: {test_parent_orm.email}")
        headers = auth_headers_for_user(test_parent_orm)

        response = client.get("/teachers/", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view this list."
        print("Parent was correctly forbidden from fetching all teachers.")

    async def test_get_all_teachers_no_auth_fails(
        self,
        client: TestClient
    ):
        """Test that an unauthenticated user cannot fetch the list of teachers."""
        print("Attempting to fetch all teachers without authentication.")
        
        response = client.get("/teachers/")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("Unauthenticated request failed as expected.")


@pytest.mark.anyio
class TestTeacherAPIPATCH:
    """Test class for PATCH endpoints of the Teachers API."""

    async def test_update_teacher_by_self_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test a teacher successfully updating their own profile."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_teacher_orm)
        update_payload = {"first_name": "UpdatedTeacherName"}
        
        print(f"Attempting to update teacher {teacher_id} as self.")
        response = client.patch(f"/teachers/{teacher_id}", headers=headers, json=update_payload)

        assert response.status_code == 200, response.json()
        updated_data = user_models.TeacherRead(**response.json())
        assert updated_data.id == teacher_id
        assert updated_data.first_name == "UpdatedTeacherName"
        print("Teacher successfully updated their own profile.")

    async def test_update_teacher_by_admin_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_admin_orm: db_models.Admins
    ):
        """Test an admin successfully updating a teacher's profile."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_admin_orm)
        update_payload = {"last_name": "AdminUpdated"}

        print(f"Admin {test_admin_orm.email} updating teacher {teacher_id}.")
        response = client.patch(f"/teachers/{teacher_id}", headers=headers, json=update_payload)

        assert response.status_code == 200, response.json()
        updated_data = user_models.TeacherRead(**response.json())
        assert updated_data.last_name == "AdminUpdated"
        print("Admin successfully updated teacher profile.")

    async def test_update_teacher_by_other_teacher_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_unrelated_teacher_orm: db_models.Teachers
    ):
        """Test that a teacher cannot update another teacher's profile."""
        target_teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_unrelated_teacher_orm)
        update_payload = {"first_name": "ForbiddenUpdate"}

        print(f"Unrelated teacher attempting to update teacher {target_teacher_id}.")
        response = client.patch(f"/teachers/{target_teacher_id}", headers=headers, json=update_payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to update this profile."
        print("Unrelated teacher was correctly forbidden from updating profile.")

    async def test_update_teacher_by_parent_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents
    ):
        """Test that a parent cannot update a teacher's profile."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_parent_orm)
        update_payload = {"first_name": "ParentUpdateAttempt"}

        print(f"Parent attempting to update teacher {teacher_id}.")
        response = client.patch(f"/teachers/{teacher_id}", headers=headers, json=update_payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to update this profile."
        print("Parent was correctly forbidden from updating teacher profile.")

    async def test_update_non_existent_teacher_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test updating a teacher that does not exist fails with 404."""
        non_existent_id = uuid4()
        headers = auth_headers_for_user(test_admin_orm)
        update_payload = {"first_name": "NonExistent"}

        print(f"Attempting to update non-existent teacher {non_existent_id}.")
        response = client.patch(f"/teachers/{non_existent_id}", headers=headers, json=update_payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "Teacher not found."
        print("Updating non-existent teacher failed as expected.")


@pytest.mark.anyio
class TestTeacherAPIDELETE:
    """Test class for DELETE endpoints of the Teachers API."""

    async def test_delete_teacher_with_active_logs_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers, # This teacher has logs from seeding
        test_admin_orm: db_models.Admins
    ):
        """Test that deleting a teacher with active tuition logs fails."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_admin_orm)

        print(f"Admin attempting to delete teacher {teacher_id} who has active logs.")
        response = client.delete(f"/teachers/{teacher_id}", headers=headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete a teacher with active tuition logs. Please void or reassign them first."
        print("Deletion of teacher with active logs failed as expected.")

    async def test_delete_teacher_by_self_success(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers # This teacher has no logs
    ):
        """Test a teacher without active logs successfully deleting their own account."""
        teacher_id = test_unrelated_teacher_orm.id
        headers = auth_headers_for_user(test_unrelated_teacher_orm)

        print(f"Teacher {teacher_id} without logs attempting to self-delete.")
        response = client.delete(f"/teachers/{teacher_id}", headers=headers)

        assert response.status_code == 204
        print("Teacher without logs successfully deleted themselves.")

    async def test_delete_teacher_by_admin_success(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers, # This teacher has no logs
        test_admin_orm: db_models.Admins
    ):
        """Test an admin successfully deleting a teacher without active logs."""
        teacher_id = test_unrelated_teacher_orm.id
        headers = auth_headers_for_user(test_admin_orm)

        print(f"Admin attempting to delete teacher {teacher_id} who has no logs.")
        response = client.delete(f"/teachers/{teacher_id}", headers=headers)

        assert response.status_code == 204
        print("Admin successfully deleted teacher without logs.")

    async def test_delete_teacher_by_parent_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents
    ):
        """Test that a parent cannot delete a teacher."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_parent_orm)

        print(f"Parent attempting to delete teacher {teacher_id}.")
        response = client.delete(f"/teachers/{teacher_id}", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to delete this profile."
        print("Parent was correctly forbidden from deleting teacher.")

    async def test_delete_non_existent_teacher_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test deleting a teacher that does not exist fails with 404."""
        non_existent_id = uuid4()
        headers = auth_headers_for_user(test_admin_orm)

        print(f"Attempting to delete non-existent teacher {non_existent_id}.")
        response = client.delete(f"/teachers/{non_existent_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Teacher not found."
        print("Deleting non-existent teacher failed as expected.")
