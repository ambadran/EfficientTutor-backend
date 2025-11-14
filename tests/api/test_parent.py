import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import MagicMock

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import user as user_models

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestParentAPIGET:
    """Test class for GET endpoints of the Parents API."""

    async def test_get_parent_by_id_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test successfully fetching a parent by their ID."""
        parent_id = test_parent_orm.id
        print(f"Attempting to fetch parent with ID: {parent_id}")

        response = client.get(f"/parents/{parent_id}")

        assert response.status_code == 200, response.json()
        parent_data = user_models.ParentRead(**response.json())
        
        assert parent_data.id == parent_id
        assert parent_data.email == test_parent_orm.email
        assert parent_data.first_name == test_parent_orm.first_name
        print(f"Successfully fetched parent {parent_id}")

    async def test_get_parent_by_id_not_found(
        self,
        client: TestClient
    ):
        """Test fetching a parent with an ID that does not exist."""
        non_existent_id = uuid4()
        print(f"Attempting to fetch non-existent parent with ID: {non_existent_id}")

        response = client.get(f"/parents/{non_existent_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Parent not found"
        print("Fetching non-existent parent failed as expected.")

    async def test_get_all_parents_as_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test that a teacher can successfully fetch the list of all parents."""
        print(f"Attempting to fetch all parents as teacher: {test_teacher_orm.email}")
        headers = auth_headers_for_user(test_teacher_orm)
        
        response = client.get("/parents/", headers=headers)

        assert response.status_code == 200, response.json()
        
        # The response should be a list of parents
        response_data = response.json()
        assert isinstance(response_data, list)
        print("Successfully fetched parents list as a teacher.")

    async def test_get_all_parents_as_parent_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test that a parent is forbidden from fetching the list of all parents."""
        print(f"Attempting to fetch all parents as parent: {test_parent_orm.email}")
        headers = auth_headers_for_user(test_parent_orm)

        response = client.get("/parents/", headers=headers)

        assert response.status_code == 403
        # Reading the exact error from `user_service.py`
        assert response.json()["detail"] == "You do not have permission to view this list. Only teachers can list parents."
        print("Parent was correctly forbidden from fetching all parents.")

    async def test_get_all_parents_no_auth_fails(
        self,
        client: TestClient
    ):
        """Test that an unauthenticated user cannot fetch the list of parents."""
        print("Attempting to fetch all parents without authentication.")
        
        response = client.get("/parents/")

        # FastAPI returns 401 Unauthorized when a token is required but not provided
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("Unauthenticated request failed as expected.")


@pytest.mark.anyio
class TestParentAPIPATCH:
    """Test class for PATCH endpoints of the Parents API."""

    async def test_update_parent_by_self_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test a parent successfully updating their own profile."""
        parent_id = test_parent_orm.id
        headers = auth_headers_for_user(test_parent_orm)
        update_payload = {
            "first_name": "UpdatedFirstName",
            "last_name": "UpdatedLastName"
        }
        
        print(f"Attempting to update parent {parent_id} as self.")
        response = client.patch(
            f"/parents/{parent_id}",
            headers=headers,
            json=update_payload
        )

        assert response.status_code == 200, response.json()
        updated_data = user_models.ParentRead(**response.json())

        assert updated_data.id == parent_id
        assert updated_data.first_name == "UpdatedFirstName"
        assert updated_data.last_name == "UpdatedLastName"
        # Ensure other fields are unchanged
        assert updated_data.email == test_parent_orm.email
        print("Parent successfully updated their own profile.")

    async def test_update_parent_by_teacher_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """Test a teacher successfully updating a parent's profile."""
        parent_id = test_parent_orm.id
        headers = auth_headers_for_user(test_teacher_orm)
        update_payload = {"first_name": "TeacherUpdatedName"}

        print(f"Attempting to update parent {parent_id} as teacher {test_teacher_orm.email}.")
        response = client.patch(
            f"/parents/{parent_id}",
            headers=headers,
            json=update_payload
        )

        assert response.status_code == 200, response.json()
        updated_data = user_models.ParentRead(**response.json())
        assert updated_data.first_name == "TeacherUpdatedName"
        print("Teacher successfully updated parent profile.")

    async def test_update_parent_by_other_parent_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_unrelated_parent_orm: db_models.Parents
    ):
        """Test that a parent cannot update another parent's profile."""
        target_parent_id = test_parent_orm.id
        # Authenticate as the unrelated parent
        headers = auth_headers_for_user(test_unrelated_parent_orm)
        update_payload = {"first_name": "ForbiddenUpdate"}

        print(f"Attempting to update parent {target_parent_id} as unrelated parent {test_unrelated_parent_orm.email}.")
        response = client.patch(
            f"/parents/{target_parent_id}",
            headers=headers,
            json=update_payload
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to update this profile."
        print("Unrelated parent was correctly forbidden from updating profile.")

    async def test_update_parent_no_auth_fails(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test that an unauthenticated user cannot update a parent profile."""
        parent_id = test_parent_orm.id
        update_payload = {"first_name": "UnauthorizedUpdate"}

        print(f"Attempting to update parent {parent_id} without authentication.")
        response = client.patch(
            f"/parents/{parent_id}",
            json=update_payload
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("Unauthenticated update failed as expected.")

    async def test_update_non_existent_parent_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test updating a parent that does not exist fails with 404."""
        non_existent_id = uuid4()
        headers = auth_headers_for_user(test_teacher_orm)
        update_payload = {"first_name": "NonExistentUpdate"}

        print(f"Attempting to update non-existent parent {non_existent_id}.")
        response = client.patch(
            f"/parents/{non_existent_id}",
            headers=headers,
            json=update_payload
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Parent not found."
        print("Updating non-existent parent failed as expected.")


@pytest.mark.anyio
class TestParentAPIDELETE:
    """Test class for DELETE endpoints of the Parents API."""

    async def test_delete_parent_by_teacher_with_students_fails(
        self,
        client: TestClient,
        test_unrelated_parent_orm: db_models.Parents, # This parent has students
        test_teacher_orm: db_models.Teachers
    ):
        """Test a teacher fails to delete a parent who has students."""
        parent_id = test_unrelated_parent_orm.id
        headers = auth_headers_for_user(test_teacher_orm)

        print(f"Attempting to delete parent {parent_id} (with students) as teacher {test_teacher_orm.email}.")
        response = client.delete(f"/parents/{parent_id}", headers=headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete a parent with associated students. Please reassign or delete the students first."
        print("Deletion of parent with students failed as expected.")

    async def test_delete_parent_with_students_fails(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents, # This parent has students
        test_teacher_orm: db_models.Teachers
    ):
        """Test that deleting a parent with associated students fails."""
        parent_id = test_parent_orm.id
        headers = auth_headers_for_user(test_teacher_orm)

        print(f"Attempting to delete parent {parent_id} (who has students) as teacher.")
        response = client.delete(f"/parents/{parent_id}", headers=headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete a parent with associated students. Please reassign or delete the students first."
        print("Deletion of parent with students failed as expected.")

    async def test_delete_parent_by_other_parent_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_unrelated_parent_orm: db_models.Parents
    ):
        """Test that a parent cannot delete another parent."""
        target_parent_id = test_parent_orm.id
        headers = auth_headers_for_user(test_unrelated_parent_orm)

        print(f"Attempting to delete parent {target_parent_id} as unrelated parent {test_unrelated_parent_orm.email}.")
        response = client.delete(f"/parents/{target_parent_id}", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to delete this profile."
        print("Unrelated parent was correctly forbidden from deleting profile.")

    async def test_delete_non_existent_parent_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test deleting a parent that does not exist fails with 404."""
        non_existent_id = uuid4()
        headers = auth_headers_for_user(test_teacher_orm)

        print(f"Attempting to delete non-existent parent {non_existent_id}.")
        response = client.delete(f"/parents/{non_existent_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Parent not found."
        print("Deleting non-existent parent failed as expected.")

