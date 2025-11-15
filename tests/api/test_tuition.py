"""
Tests for the /tuitions API endpoints.
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.models import tuition as tuition_models
from src.efficient_tutor_backend.models import meeting_links as meeting_link_models
from src.efficient_tutor_backend.database.db_enums import MeetingLinkTypeEnum
from src.efficient_tutor_backend.services.security import JWTHandler
from tests.constants import TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_TUITION_ID, TEST_TUITION_ID_NO_LINK

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestTuitionAPIGET:
    """Test class for GET endpoints of the Tuitions API."""

    async def test_list_tuitions_as_teacher_success(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test a teacher successfully listing their tuitions."""
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get("/tuitions/", headers=headers)
        assert response.status_code == 200
        tuitions = response.json()
        assert isinstance(tuitions, list)
        assert len(tuitions) > 0
        # The response should be a list of TuitionReadForTeacher models
        assert "charges" in tuitions[0]
        if tuitions[0]["charges"]:
            assert "student" in tuitions[0]["charges"][0]
        assert "student" in tuitions[0]["charges"][0]

    async def test_list_tuitions_as_parent_success(
        self, client: TestClient, test_parent_orm: db_models.Users
    ):
        """Test a parent successfully listing their tuitions."""
        headers = auth_headers_for_user(test_parent_orm)
        response = client.get("/tuitions/", headers=headers)
        assert response.status_code == 200
        tuitions = response.json()
        assert isinstance(tuitions, list)
        assert len(tuitions) > 0
        # The response should be a list of TuitionReadForParent models
        assert "charge" in tuitions[0]

    async def test_list_tuitions_as_student_success(
        self, client: TestClient, test_student_orm: db_models.Users
    ):
        """Test a student successfully listing their tuitions."""
        headers = auth_headers_for_user(test_student_orm)
        response = client.get("/tuitions/", headers=headers)
        assert response.status_code == 200
        tuitions = response.json()
        assert isinstance(tuitions, list)
        assert len(tuitions) > 0
        # The response should be a list of TuitionReadForStudent models
        assert "attendee_names" in tuitions[0]
        assert "charges" not in tuitions[0] # Students shouldn't see charges

    async def test_get_tuition_by_id_as_teacher_success(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test a teacher fetching a specific tuition they own."""
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get(f"/tuitions/{TEST_TUITION_ID}", headers=headers)
        assert response.status_code == 200
        tuition = response.json()
        assert tuition["id"] == str(TEST_TUITION_ID)
        assert "charges" in tuition
        assert "student" in tuition["charges"][0]

    async def test_get_tuition_by_id_as_unrelated_teacher_forbidden(
        self, client: TestClient, test_unrelated_teacher_orm: db_models.Users
    ):
        """Test an unrelated teacher is forbidden to fetch a tuition."""
        headers = auth_headers_for_user(test_unrelated_teacher_orm)
        response = client.get(f"/tuitions/{TEST_TUITION_ID}", headers=headers)
        assert response.status_code == 403 # Service layer raises 403 for not found/forbidden

    async def test_get_tuition_by_id_not_found(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test fetching a non-existent tuition returns 404."""
        headers = auth_headers_for_user(test_teacher_orm)
        non_existent_id = uuid4()
        response = client.get(f"/tuitions/{non_existent_id}", headers=headers)
        assert response.status_code == 404


@pytest.mark.anyio
class TestTuitionAPIPATCH:
    """Test class for PATCH endpoints of the Tuitions API."""

    async def test_update_tuition_as_owner_teacher_success(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test the owning teacher can update a tuition."""
        headers = auth_headers_for_user(test_teacher_orm)
        update_data = {"max_duration_minutes": 75}
        response = client.patch(f"/tuitions/{TEST_TUITION_ID}", headers=headers, json=update_data)
        assert response.status_code == 200
        updated_tuition = tuition_models.TuitionReadForTeacher(**response.json())
        assert updated_tuition.max_duration_minutes == 75

    async def test_update_tuition_as_unrelated_teacher_forbidden(
        self, client: TestClient, test_unrelated_teacher_orm: db_models.Users
    ):
        """Test an unrelated teacher is forbidden from updating a tuition."""
        headers = auth_headers_for_user(test_unrelated_teacher_orm)
        update_data = {"max_duration_minutes": 90}
        response = client.patch(f"/tuitions/{TEST_TUITION_ID}", headers=headers, json=update_data)
        assert response.status_code == 403 # Service raises 403 for forbidden access

    async def test_update_tuition_as_parent_forbidden(
        self, client: TestClient, test_parent_orm: db_models.Users
    ):
        """Test a parent is forbidden from updating a tuition."""
        headers = auth_headers_for_user(test_parent_orm)
        update_data = {"max_duration_minutes": 90}
        response = client.patch(f"/tuitions/{TEST_TUITION_ID}", headers=headers, json=update_data)
        assert response.status_code == 403


@pytest.mark.anyio
class TestMeetingLinkAPI:
    """Test class for the meeting link sub-resource endpoints."""

    async def test_create_meeting_link_as_owner_teacher_success(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test creating a meeting link for a tuition."""
        headers = auth_headers_for_user(test_teacher_orm)
        link_data = {
            "meeting_link": "https://meet.google.com/new-link",
            "meeting_link_type": MeetingLinkTypeEnum.GOOGLE_MEET.value
        }
        # Use the tuition that is known to have no link
        tuition_id_to_use = TEST_TUITION_ID_NO_LINK

        response = client.post(f"/tuitions/{tuition_id_to_use}/meeting_link", headers=headers, json=link_data)
        assert response.status_code == 201
        new_link = meeting_link_models.MeetingLinkRead(**response.json())
        assert str(new_link.meeting_link) == link_data["meeting_link"]

    async def test_update_meeting_link_success(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test updating an existing meeting link."""
        headers = auth_headers_for_user(test_teacher_orm)
        update_data = {"meeting_link": "https://meet.google.com/updated-link"}
        response = client.patch(f"/tuitions/{TEST_TUITION_ID}/meeting_link", headers=headers, json=update_data)
        assert response.status_code == 200
        updated_link = meeting_link_models.MeetingLinkRead(**response.json())
        assert str(updated_link.meeting_link) == update_data["meeting_link"]

    async def test_delete_meeting_link_success(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test deleting a meeting link."""
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.delete(f"/tuitions/{TEST_TUITION_ID}/meeting_link", headers=headers)
        assert response.status_code == 204

@pytest.mark.anyio
class TestTuitionRegeneration:
    """Test class for the tuition regeneration endpoint."""

    async def test_regenerate_tuitions_as_admin_success(
        self, client: TestClient, test_admin_orm: db_models.Users
    ):
        """Test that an admin can trigger tuition regeneration."""
        headers = auth_headers_for_user(test_admin_orm)
        response = client.post("/tuitions/regenerate", headers=headers)
        assert response.status_code == 202
        assert response.json() == {"message": "Tuition regeneration process started successfully."}

    async def test_regenerate_tuitions_as_teacher_forbidden(
        self, client: TestClient, test_teacher_orm: db_models.Users
    ):
        """Test that a teacher is forbidden from regenerating tuitions."""
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.post("/tuitions/regenerate", headers=headers)
        assert response.status_code == 403

    async def test_regenerate_tuitions_as_parent_forbidden(
        self, client: TestClient, test_parent_orm: db_models.Users
    ):
        """Test that a parent is forbidden from regenerating tuitions."""
        headers = auth_headers_for_user(test_parent_orm)
        response = client.post("/tuitions/regenerate", headers=headers)
        assert response.status_code == 403
