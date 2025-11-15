import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import AdminPrivilegeType

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestAdminAPIGET:
    """Test class for GET endpoints of the Admins API."""

    async def test_get_admin_by_id_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test successfully fetching an admin by their ID."""
        admin_id = test_admin_orm.id
        print(f"Attempting to fetch admin with ID: {admin_id}")

        response = client.get(f"/admins/{admin_id}")

        assert response.status_code == 200, response.json()
        admin_data = user_models.AdminRead(**response.json())
        
        assert admin_data.id == admin_id
        assert admin_data.email == test_admin_orm.email
        assert admin_data.first_name == test_admin_orm.first_name
        print(f"Successfully fetched admin {admin_id}")

    async def test_get_admin_by_id_not_found(
        self,
        client: TestClient
    ):
        """Test fetching an admin with an ID that does not exist."""
        non_existent_id = uuid4()
        print(f"Attempting to fetch non-existent admin with ID: {non_existent_id}")

        response = client.get(f"/admins/{non_existent_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Admin not found"
        print("Fetching non-existent admin failed as expected.")

    async def test_get_all_admins_as_master_admin_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins # Master admin
    ):
        """Test that a master admin can successfully fetch the list of all admins."""
        print(f"Attempting to fetch all admins as master admin: {test_admin_orm.email}")
        headers = auth_headers_for_user(test_admin_orm)
        
        response = client.get("/admins/", headers=headers)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        print("Successfully fetched admins list as a master admin.")

    async def test_get_all_admins_as_normal_admin_forbidden(
        self,
        client: TestClient,
        test_normal_admin_orm: db_models.Admins
    ):
        """Test that a normal admin is forbidden from fetching the list of all admins."""
        print(f"Attempting to fetch all admins as normal admin: {test_normal_admin_orm.email}")
        headers = auth_headers_for_user(test_normal_admin_orm)

        response = client.get("/admins/", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "Only a Master admin can view the list of all admins."
        print("Normal admin was correctly forbidden from fetching all admins.")

    async def test_get_all_admins_as_teacher_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test that a non-admin user (teacher) is forbidden from fetching the admin list."""
        print(f"Attempting to fetch all admins as teacher: {test_teacher_orm.email}")
        headers = auth_headers_for_user(test_teacher_orm)

        response = client.get("/admins/", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view this list."
        print("Teacher was correctly forbidden from fetching all admins.")

    async def test_get_all_admins_no_auth_fails(
        self,
        client: TestClient
    ):
        """Test that an unauthenticated user cannot fetch the list of admins."""
        print("Attempting to fetch all admins without authentication.")
        
        response = client.get("/admins/")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("Unauthenticated request failed as expected.")


@pytest.mark.anyio
class TestAdminAPIPATCH:
    """Test class for PATCH endpoints of the Admins API."""

    async def test_update_admin_by_self_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test an admin successfully updating their own profile."""
        admin_id = test_admin_orm.id
        headers = auth_headers_for_user(test_admin_orm)
        update_payload = {"first_name": "UpdatedMaster"}
        
        print(f"Attempting to update admin {admin_id} as self.")
        response = client.patch(f"/admins/{admin_id}", headers=headers, json=update_payload)

        assert response.status_code == 200, response.json()
        updated_data = user_models.AdminRead(**response.json())

        assert updated_data.id == admin_id
        assert updated_data.first_name == "UpdatedMaster"
        print("Admin successfully updated their own profile.")

    async def test_update_admin_by_self_privilege_change_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test an admin fails to change their own privilege level."""
        admin_id = test_admin_orm.id
        headers = auth_headers_for_user(test_admin_orm)
        update_payload = {"privileges": AdminPrivilegeType.NORMAL.value}

        print(f"Attempting to change own privilege for admin {admin_id}.")
        response = client.patch(f"/admins/{admin_id}", headers=headers, json=update_payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "You cannot change your own privilege level."
        print("Admin correctly failed to change own privilege.")

    async def test_update_other_admin_by_master_admin_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins, # Master
        test_normal_admin_orm: db_models.Admins # Normal
    ):
        """Test a master admin successfully updating another admin's profile."""
        target_admin_id = test_normal_admin_orm.id
        headers = auth_headers_for_user(test_admin_orm)
        update_payload = {"last_name": "MasterUpdated"}

        print(f"Master admin {test_admin_orm.email} updating normal admin {target_admin_id}.")
        response = client.patch(f"/admins/{target_admin_id}", headers=headers, json=update_payload)

        assert response.status_code == 200, response.json()
        updated_data = user_models.AdminRead(**response.json())
        assert updated_data.last_name == "MasterUpdated"
        print("Master admin successfully updated another admin.")

    async def test_update_other_admin_by_normal_admin_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins, # Master
        test_normal_admin_orm: db_models.Admins # Normal
    ):
        """Test a normal admin fails to update another admin's profile."""
        target_admin_id = test_admin_orm.id
        headers = auth_headers_for_user(test_normal_admin_orm)
        update_payload = {"first_name": "ForbiddenUpdate"}

        print(f"Normal admin {test_normal_admin_orm.email} attempting to update master admin {target_admin_id}.")
        response = client.patch(f"/admins/{target_admin_id}", headers=headers, json=update_payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "Only a Master admin can update other admin profiles."
        print("Normal admin was correctly forbidden from updating another admin.")

    async def test_update_admin_to_master_privilege_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins,
        test_normal_admin_orm: db_models.Admins
    ):
        """Test a master admin fails to promote another admin to master."""
        target_admin_id = test_normal_admin_orm.id
        headers = auth_headers_for_user(test_admin_orm)
        update_payload = {"privileges": AdminPrivilegeType.MASTER.value}

        print(f"Master admin attempting to promote {target_admin_id} to master.")
        response = client.patch(f"/admins/{target_admin_id}", headers=headers, json=update_payload)

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot assign Master privilege. This must be done via a dedicated transfer process."
        print("Promotion to master privilege failed as expected.")

    async def test_update_non_existent_admin_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test updating an admin that does not exist fails with 404."""
        non_existent_id = uuid4()
        headers = auth_headers_for_user(test_admin_orm)
        update_payload = {"first_name": "NonExistent"}

        print(f"Attempting to update non-existent admin {non_existent_id}.")
        response = client.patch(f"/admins/{non_existent_id}", headers=headers, json=update_payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "Admin not found."
        print("Updating non-existent admin failed as expected.")


@pytest.mark.anyio
class TestAdminAPIDELETE:
    """Test class for DELETE endpoints of the Admins API."""

    async def test_delete_other_admin_by_master_admin_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins,
        test_normal_admin_orm: db_models.Admins
    ):
        """Test a master admin successfully deleting another admin."""
        target_admin_id = test_normal_admin_orm.id
        headers = auth_headers_for_user(test_admin_orm)

        print(f"Master admin attempting to delete normal admin {target_admin_id}.")
        delete_response = client.delete(f"/admins/{target_admin_id}", headers=headers)

        assert delete_response.status_code == 204
        print("Successfully received 204 No Content on admin deletion.")

    async def test_delete_admin_by_normal_admin_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins,
        test_normal_admin_orm: db_models.Admins
    ):
        """Test a normal admin fails to delete another admin."""
        target_admin_id = test_admin_orm.id
        headers = auth_headers_for_user(test_normal_admin_orm)

        print(f"Normal admin {test_normal_admin_orm.email} attempting to delete master admin {target_admin_id}.")
        response = client.delete(f"/admins/{target_admin_id}", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "Only a Master admin can delete other admins."
        print("Normal admin was correctly forbidden from deleting another admin.")

    async def test_delete_self_by_master_admin_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test a master admin fails to delete their own account."""
        admin_id = test_admin_orm.id
        headers = auth_headers_for_user(test_admin_orm)

        print(f"Master admin {admin_id} attempting to self-delete.")
        response = client.delete(f"/admins/{admin_id}", headers=headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "You cannot delete your own account."
        print("Self-deletion failed as expected.")

    async def test_delete_non_existent_admin_fails(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test deleting an admin that does not exist fails with 404."""
        non_existent_id = uuid4()
        headers = auth_headers_for_user(test_admin_orm)

        print(f"Attempting to delete non-existent admin {non_existent_id}.")
        response = client.delete(f"/admins/{non_existent_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Admin not found."
        print("Deleting non-existent admin failed as expected.")

    async def test_delete_admin_no_auth_fails(
        self,
        client: TestClient,
        test_normal_admin_orm: db_models.Admins
    ):
        """Test that an unauthenticated user cannot delete an admin."""
        target_admin_id = test_normal_admin_orm.id
        print(f"Attempting to delete admin {target_admin_id} without authentication.")
        
        response = client.delete(f"/admins/{target_admin_id}")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("Unauthenticated delete request failed as expected.")
