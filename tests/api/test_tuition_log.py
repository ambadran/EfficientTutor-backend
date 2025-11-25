import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import finance as finance_models
from src.efficient_tutor_backend.database.db_enums import EducationalSystemEnum
from tests.constants import (
    TEST_TEACHER_ID,
    TEST_PARENT_ID,
    TEST_STUDENT_ID,
    TEST_TUITION_LOG_ID_SCHEDULED,
    TEST_TUITION_LOG_ID_CUSTOM,
    TEST_UNRELATED_TEACHER_ID
)

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestTuitionLogsAPIGET:
    """Test class for GET endpoints of the Tuition Logs API."""

    async def test_list_logs_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test successfully listing tuition logs for a teacher."""
        print(f"Attempting to list logs as teacher: {test_teacher_orm.email}")
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get("/tuition-logs/", headers=headers)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0
        
        # Validate the dictionary directly
        log_entry_dict = response_data[0]
        assert log_entry_dict['teacher']['id'] == str(test_teacher_orm.id)
        assert 'total_cost' in log_entry_dict
        print("Successfully listed logs for teacher.")

    async def test_list_logs_as_parent(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test successfully listing tuition logs for a parent."""
        print(f"Attempting to list logs as parent: {test_parent_orm.email}")
        headers = auth_headers_for_user(test_parent_orm)
        response = client.get("/tuition-logs/", headers=headers)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0

        # Validate the dictionary directly
        log_entry_dict = response_data[0]
        assert 'cost' in log_entry_dict
        assert float(log_entry_dict['cost']) > 0
        print("Successfully listed logs for parent.")

    async def test_list_logs_as_student(
        self,
        client: TestClient,
        test_student_orm: db_models.Students
    ):
        """Test that listing tuition logs as a student is forbidden."""
        print(f"Attempting to list logs as student: {test_student_orm.email}")
        headers = auth_headers_for_user(test_student_orm)
        response = client.get("/tuition-logs/", headers=headers)

        assert response.status_code == 403, response.json()
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Listing logs as student failed as expected.")

    async def test_list_logs_unauthenticated(self, client: TestClient):
        """Test listing logs fails without authentication."""
        response = client.get("/tuition-logs/")
        assert response.status_code == 401
        print("Listing logs failed without authentication as expected.")

    async def test_get_log_by_id_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test getting a single log by ID as the owning teacher."""
        log_id = TEST_TUITION_LOG_ID_SCHEDULED
        print(f"Teacher {test_teacher_orm.email} fetching log {log_id}")
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get(f"/tuition-logs/{log_id}", headers=headers)

        assert response.status_code == 200, response.json()
        log_entry_dict = response.json()
        assert log_entry_dict['id'] == str(log_id)
        assert log_entry_dict['teacher']['id'] == str(test_teacher_orm.id)
        print("Successfully fetched log by ID for teacher.")

    async def test_get_log_by_id_as_parent(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test getting a single log by ID as a relevant parent."""
        log_id = TEST_TUITION_LOG_ID_SCHEDULED
        print(f"Parent {test_parent_orm.email} fetching log {log_id}")
        headers = auth_headers_for_user(test_parent_orm)
        response = client.get(f"/tuition-logs/{log_id}", headers=headers)

        assert response.status_code == 200, response.json()
        log_entry_dict = response.json()
        assert log_entry_dict['id'] == str(log_id)
        assert float(log_entry_dict['cost']) > 0
        print("Successfully fetched log by ID for parent.")

    async def test_get_log_by_id_as_unrelated_user(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers
    ):
        """Test that an unrelated user cannot access a tuition log."""
        log_id = TEST_TUITION_LOG_ID_SCHEDULED
        print(f"Unrelated teacher {test_unrelated_teacher_orm.email} attempting to fetch log {log_id}")
        headers = auth_headers_for_user(test_unrelated_teacher_orm)
        response = client.get(f"/tuition-logs/{log_id}", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view this log."
        print("Unrelated user was correctly denied access.")

    async def test_get_log_by_id_not_found(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test fetching a log with an ID that does not exist."""
        non_existent_id = UUID("00000000-0000-0000-0000-000000000000")
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get(f"/tuition-logs/{non_existent_id}", headers=headers)

        assert response.status_code == 404
        print("Fetching non-existent log failed as expected.")


@pytest.mark.anyio
class TestTuitionLogsAPIPOST:
    """Test class for POST endpoints of the Tuition Logs API."""

    async def test_create_custom_log_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students,
    ):
        """Test a teacher successfully creating a 'custom' tuition log."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=1)
        
        payload = {
            "log_type": "CUSTOM",
            "subject": "Math",
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "lesson_index": 5,
            "charges": [
                {
                    "student_id": str(test_student_orm.id),
                    "cost": "150.00"
                }
            ]
        }
        
        response = client.post("/tuition-logs/", headers=headers, json=payload)
        
        assert response.status_code == 201, response.json()
        
        response_data = response.json()
        assert response_data["subject"] == "Math"
        assert response_data["total_cost"] == "150.00"
        assert response_data["create_type"] == "CUSTOM"
        assert len(response_data["charges"]) == 1
        assert response_data["charges"][0]["student_id"] == str(test_student_orm.id)
        print("Successfully created custom tuition log.")

    async def test_create_scheduled_log_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_tuition_orm: db_models.Tuitions,
    ):
        """Test a teacher successfully creating a 'scheduled' tuition log."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        # Ensure the test tuition belongs to the test teacher
        assert test_tuition_orm.teacher_id == test_teacher_orm.id

        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=1)
        
        payload = {
            "log_type": "SCHEDULED",
            "tuition_id": str(test_tuition_orm.id),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        
        response = client.post("/tuition-logs/", headers=headers, json=payload)
        
        assert response.status_code == 201, response.json()
        
        response_data = response.json()
        assert response_data["create_type"] == "SCHEDULED"
        assert response_data["tuition_id"] == str(test_tuition_orm.id)
        assert response_data["subject"] == test_tuition_orm.subject
        # The cost should be inherited from the tuition template
        assert response_data["total_cost"] == str(sum(c.cost for c in test_tuition_orm.tuition_template_charges))
        print("Successfully created scheduled tuition log.")

    async def test_create_log_as_parent_is_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent is forbidden from creating a tuition log."""
        headers = auth_headers_for_user(test_parent_orm)
        
        payload = {
            "log_type": "CUSTOM",
            "subject": "Math",
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "lesson_index": 1,
            "charges": [{"student_id": str(UUID(int=0)), "cost": "50.00"}]
        }
        
        response = client.post("/tuition-logs/", headers=headers, json=payload)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Parent was correctly forbidden from creating a log.")

    async def test_create_scheduled_log_for_unowned_tuition_is_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_unrelated_teacher_orm: db_models.Teachers,
        test_tuition_orm: db_models.Tuitions,
    ):
        """Test that a teacher cannot create a scheduled log for a tuition they do not own (IDOR)."""
        # Ensure the tuition belongs to the main test teacher, not the unrelated one
        assert test_tuition_orm.teacher_id == test_teacher_orm.id
        assert test_tuition_orm.teacher_id != test_unrelated_teacher_orm.id

        # The unrelated teacher attempts to log a class for the main teacher's tuition
        headers = auth_headers_for_user(test_unrelated_teacher_orm)
        
        payload = {
            "log_type": "SCHEDULED",
            "tuition_id": str(test_tuition_orm.id),
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
        
        response = client.post("/tuition-logs/", headers=headers, json=payload)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to log this tuition."
        print("Unrelated teacher was correctly forbidden from logging unowned tuition.")

    async def test_create_custom_log_with_nonexistent_student_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that creating a custom log with a non-existent student ID fails."""
        headers = auth_headers_for_user(test_teacher_orm)
        non_existent_student_id = uuid4()

        payload = {
            "log_type": "CUSTOM",
            "subject": "Math",
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "lesson_index": 1,
            "charges": [
                {
                    "student_id": str(non_existent_student_id),
                    "cost": "100.00"
                }
            ]
        }

        response = client.post("/tuition-logs/", headers=headers, json=payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "One or more students not found."
        print("Creating log with non-existent student failed as expected.")


@pytest.mark.anyio
class TestTuitionLogsAPIPATCH:
    """Test class for PATCH endpoints of the Tuition Logs API."""

    async def test_void_log_as_owner_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that the owning teacher can successfully void a tuition log."""
        log_id_to_void = TEST_TUITION_LOG_ID_CUSTOM
        headers = auth_headers_for_user(test_teacher_orm)

        # 1. Void the log
        response_void = client.patch(f"/tuition-logs/{log_id_to_void}/void", headers=headers)

        assert response_void.status_code == 200
        assert response_void.json() == {"message": "Tuition log voided successfully."}

    async def test_void_log_as_unrelated_teacher_is_forbidden(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers,
    ):
        """Test that an unrelated teacher is forbidden from voiding a log."""
        log_id_to_void = TEST_TUITION_LOG_ID_CUSTOM
        headers = auth_headers_for_user(test_unrelated_teacher_orm)

        response = client.patch(f"/tuition-logs/{log_id_to_void}/void", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to void this log."
        print("Unrelated teacher was correctly forbidden from voiding a log.")

    async def test_void_log_as_parent_is_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent is forbidden from voiding a log."""
        log_id_to_void = TEST_TUITION_LOG_ID_CUSTOM
        headers = auth_headers_for_user(test_parent_orm)

        response = client.patch(f"/tuition-logs/{log_id_to_void}/void", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Parent was correctly forbidden from voiding a log.")


@pytest.mark.anyio
class TestTuitionLogsAPICorrection:
    """Test class for the correction endpoint."""

    async def test_correct_log_as_owner_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students,
    ):
        """Test that the owning teacher can successfully correct a tuition log."""
        old_log_id = TEST_TUITION_LOG_ID_SCHEDULED
        headers = auth_headers_for_user(test_teacher_orm)

        # 1. Define the correction data
        correction_payload = {
            "log_type": "CUSTOM",
            "subject": "Biology",
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "lesson_index": 101,
            "charges": [{"student_id": str(test_student_orm.id), "cost": "250.00"}]
        }

        # 2. Make the correction request
        response_correction = client.post(
            f"/tuition-logs/{old_log_id}/correction",
            headers=headers,
            json=correction_payload
        )

        # 3. Assert the response for the new log
        assert response_correction.status_code == 200, response_correction.json()
        new_log_data = response_correction.json()
        
        assert new_log_data["id"] != old_log_id
        assert new_log_data["subject"] == "Biology"
        assert new_log_data["total_cost"] == "250.00"
        assert new_log_data["corrected_from_log_id"] == str(old_log_id)
        print("Successfully created new corrected log.")

    async def test_correct_log_as_unrelated_teacher_is_forbidden(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers,
    ):
        """Test that an unrelated teacher is forbidden from correcting a log."""
        old_log_id = TEST_TUITION_LOG_ID_SCHEDULED
        headers = auth_headers_for_user(test_unrelated_teacher_orm)

        # A valid payload is needed to get past the Pydantic validation layer
        # and actually test the authorization logic in the service.
        correction_payload = {
            "log_type": "CUSTOM",
            "subject": "Biology",
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "lesson_index": 101,
            "charges": [{"student_id": str(uuid4()), "cost": "250.00"}]
        }

        response = client.post(
            f"/tuition-logs/{old_log_id}/correction",
            headers=headers,
            json=correction_payload
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to edit this log."
        print("Unrelated teacher was correctly forbidden from correcting a log.")

    async def test_correct_log_as_parent_is_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent is forbidden from correcting a log."""
        old_log_id = TEST_TUITION_LOG_ID_SCHEDULED
        headers = auth_headers_for_user(test_parent_orm)

        # A valid payload is needed to get past Pydantic validation
        correction_payload = {
            "log_type": "CUSTOM",
            "subject": "Biology",
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "lesson_index": 101,
            "charges": [{"student_id": str(uuid4()), "cost": "250.00"}]
        }

        response = client.post(
            f"/tuition-logs/{old_log_id}/correction",
            headers=headers,
            json=correction_payload
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Parent was correctly forbidden from correcting a log.")


