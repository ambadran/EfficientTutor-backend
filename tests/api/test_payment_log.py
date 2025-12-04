import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from tests.constants import (
    TEST_PAYMENT_LOG_ID,
    TEST_PARENT_ID,
    TEST_TEACHER_ID,
    TEST_UNRELATED_TEACHER_ID,
    TEST_UNRELATED_PARENT_ID,
    TEST_PAYMENT_LOG_ID_UNRELATED,
    TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT,
    TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER,
)

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestPaymentLogsAPIGET:
    """Test class for GET endpoints of the Payment Logs API."""

    async def test_list_logs_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test successfully listing payment logs for a teacher."""
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get("/payment-logs/", headers=headers)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0
        
        # Find the specific log we are interested in from the list
        target_log = next((log for log in response_data if log["id"] == str(TEST_PAYMENT_LOG_ID)), None)
        assert target_log is not None, f"Log with ID {TEST_PAYMENT_LOG_ID} not found in response."

        expected_teacher_name = f"{test_teacher_orm.first_name} {test_teacher_orm.last_name}"
        assert target_log["teacher_name"] == expected_teacher_name
        print("Successfully listed payment logs for teacher.")

    async def test_list_logs_as_parent(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test successfully listing payment logs for a parent."""
        headers = auth_headers_for_user(test_parent_orm)
        response = client.get("/payment-logs/", headers=headers)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0
        
        target_log = next((log for log in response_data if log["id"] == str(TEST_PAYMENT_LOG_ID)), None)
        assert target_log is not None, f"Log with ID {TEST_PAYMENT_LOG_ID} not found in response."

        expected_parent_name = f"{test_parent_orm.first_name} {test_parent_orm.last_name}"
        assert target_log["parent_name"] == expected_parent_name
        print("Successfully listed payment logs for parent.")

    async def test_list_logs_as_student_is_forbidden(
        self,
        client: TestClient,
        test_student_orm: db_models.Students
    ):
        """Test that a student is forbidden from listing payment logs."""
        headers = auth_headers_for_user(test_student_orm)
        response = client.get("/payment-logs/", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "User with role 'student' is not authorized to view payment logs."
        print("Student was correctly forbidden from listing payment logs.")

    async def test_get_log_by_id_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test getting a single payment log by ID as the owning teacher."""
        log_id = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get(f"/payment-logs/{log_id}", headers=headers)

        assert response.status_code == 200, response.json()
        log_entry = response.json()
        assert log_entry['id'] == str(log_id)
        expected_teacher_name = f"{test_teacher_orm.first_name} {test_teacher_orm.last_name}"
        assert log_entry['teacher_name'] == expected_teacher_name
        print("Successfully fetched payment log by ID for teacher.")

    async def test_get_log_by_id_as_parent(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Test getting a single payment log by ID as the related parent."""
        log_id = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_parent_orm)
        response = client.get(f"/payment-logs/{log_id}", headers=headers)

        assert response.status_code == 200, response.json()
        log_entry = response.json()
        assert log_entry['id'] == str(log_id)
        expected_parent_name = f"{test_parent_orm.first_name} {test_parent_orm.last_name}"
        assert log_entry['parent_name'] == expected_parent_name
        print("Successfully fetched payment log by ID for parent.")

    async def test_get_log_by_id_as_unrelated_user_is_forbidden(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers
    ):
        """Test that an unrelated user is forbidden from fetching a payment log."""
        log_id = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_unrelated_teacher_orm)
        response = client.get(f"/payment-logs/{log_id}", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view this log."
        print("Unrelated user was correctly forbidden from fetching a payment log.")

    async def test_get_log_by_id_not_found(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test fetching a payment log with an ID that does not exist."""
        non_existent_id = uuid4()
        headers = auth_headers_for_user(test_teacher_orm)
        response = client.get(f"/payment-logs/{non_existent_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Payment log not found."
        print("Fetching non-existent payment log failed as expected.")


@pytest.mark.anyio
class TestPaymentLogsAPIPOST:
    """Test class for POST endpoints of the Payment Logs API."""

    async def test_create_payment_log_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents,
    ):
        """Test a teacher successfully creating a payment log."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        payload = {
            "parent_id": str(test_parent_orm.id),
            "teacher_id": str(test_teacher_orm.id),
            "amount_paid": "250.75",
            "payment_date": datetime.now(timezone.utc).isoformat(),
            "notes": "Test payment log creation."
        }
        
        response = client.post("/payment-logs/", headers=headers, json=payload)
        
        assert response.status_code == 201, response.json()
        
        response_data = response.json()
        assert response_data["amount_paid"] == "250.75"
        assert response_data["notes"] == "Test payment log creation."
        
        expected_teacher_name = f"{test_teacher_orm.first_name} {test_teacher_orm.last_name}"
        assert response_data["teacher_name"] == expected_teacher_name
        
        expected_parent_name = f"{test_parent_orm.first_name} {test_parent_orm.last_name}"
        assert response_data["parent_name"] == expected_parent_name
        
        print("Successfully created payment log.")

    async def test_create_payment_log_as_parent_is_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent is forbidden from creating a payment log."""
        headers = auth_headers_for_user(test_parent_orm)
        
        # Dummy payload, as authorization should be checked first
        payload = {
            "parent_id": str(test_parent_orm.id),
            "teacher_id": str(uuid4()),
            "amount_paid": "100.00",
            "payment_date": datetime.now(timezone.utc).isoformat(),
        }
        
        response = client.post("/payment-logs/", headers=headers, json=payload)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Parent was correctly forbidden from creating a payment log.")

    async def test_create_payment_log_for_other_teacher_is_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_unrelated_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a teacher cannot create a payment log for another teacher (IDOR)."""
        # Authenticate as the main teacher
        headers = auth_headers_for_user(test_teacher_orm)
        
        # But try to create a log for the unrelated teacher
        payload = {
            "parent_id": str(test_parent_orm.id),
            "teacher_id": str(test_unrelated_teacher_orm.id), # IDOR attempt
            "amount_paid": "100.00",
            "payment_date": datetime.now(timezone.utc).isoformat(),
        }
        
        response = client.post("/payment-logs/", headers=headers, json=payload)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You can only create payment logs for yourself."
        print("Teacher was correctly forbidden from creating a payment log for another teacher.")

    async def test_create_payment_log_for_nonexistent_parent_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that creating a payment log for a non-existent parent fails."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        payload = {
            "parent_id": str(uuid4()), # Non-existent parent
            "teacher_id": str(test_teacher_orm.id),
            "amount_paid": "100.00",
            "payment_date": datetime.now(timezone.utc).isoformat(),
        }
        
        response = client.post("/payment-logs/", headers=headers, json=payload)
        
        # The service has been fixed to handle this case gracefully.
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        print("Creating payment log for non-existent parent failed as expected.")


@pytest.mark.anyio
class TestPaymentLogsAPIPATCH:
    """Test class for PATCH endpoints of the Payment Logs API."""

    async def test_void_log_as_owner_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that the owning teacher can successfully void a payment log."""
        log_id_to_void = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_teacher_orm)

        # 1. Void the log
        response_void = client.patch(f"/payment-logs/{log_id_to_void}/void", headers=headers)

        assert response_void.status_code == 200
        assert response_void.json() == {"message": "Payment log voided successfully."}

    async def test_void_log_as_unrelated_teacher_is_forbidden(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers,
    ):
        """Test that an unrelated teacher is forbidden from voiding a payment log."""
        log_id_to_void = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_unrelated_teacher_orm)

        response = client.patch(f"/payment-logs/{log_id_to_void}/void", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to void this log."
        print("Unrelated teacher was correctly forbidden from voiding a payment log.")

    async def test_void_log_as_parent_is_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent is forbidden from voiding a payment log."""
        log_id_to_void = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_parent_orm)

        response = client.patch(f"/payment-logs/{log_id_to_void}/void", headers=headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Parent was correctly forbidden from voiding a payment log.")


@pytest.mark.anyio
class TestPaymentLogsAPICorrection:
    """Test class for the correction endpoint of the Payment Logs API."""

    async def test_correct_log_as_owner_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents,
    ):
        """Test that the owning teacher can successfully correct a payment log."""
        old_log_id = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_teacher_orm)

        # 1. Define the correction data with a different amount
        correction_payload = {
            "parent_id": str(test_parent_orm.id),
            "teacher_id": str(test_teacher_orm.id),
            "amount_paid": "300.00",
            "payment_date": datetime.now(timezone.utc).isoformat(),
            "notes": "Corrected payment."
        }

        # 2. Make the correction request
        response_correction = client.post(
            f"/payment-logs/{old_log_id}/correction",
            headers=headers,
            json=correction_payload
        )

        # 3. Assert the response for the new log
        assert response_correction.status_code == 200, response_correction.json()
        new_log_data = response_correction.json()
        
        assert new_log_data["id"] != old_log_id
        assert new_log_data["amount_paid"] == "300.00"
        assert new_log_data["notes"] == "Corrected payment."
        assert new_log_data["corrected_from_log_id"] == str(old_log_id)
        print("Successfully created new corrected payment log.")

    async def test_correct_log_as_unrelated_teacher_is_forbidden(
        self,
        client: TestClient,
        test_unrelated_teacher_orm: db_models.Teachers,
    ):
        """Test that an unrelated teacher is forbidden from correcting a payment log."""
        old_log_id = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_unrelated_teacher_orm)

        # A valid payload is needed to get past Pydantic validation
        correction_payload = {
            "parent_id": str(uuid4()),
            "teacher_id": str(test_unrelated_teacher_orm.id),
            "amount_paid": "100.00",
            "payment_date": datetime.now(timezone.utc).isoformat(),
        }

        response = client.post(
            f"/payment-logs/{old_log_id}/correction",
            headers=headers,
            json=correction_payload
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to void this log."
        print("Unrelated teacher was correctly forbidden from correcting a payment log.")

    async def test_correct_log_as_parent_is_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent is forbidden from correcting a payment log."""
        old_log_id = TEST_PAYMENT_LOG_ID
        headers = auth_headers_for_user(test_parent_orm)

        # A valid payload is needed to get past Pydantic validation
        correction_payload = {
            "parent_id": str(test_parent_orm.id),
            "teacher_id": str(uuid4()),
            "amount_paid": "100.00",
            "payment_date": datetime.now(timezone.utc).isoformat(),
        }

        response = client.post(
            f"/payment-logs/{old_log_id}/correction",
            headers=headers,
            json=correction_payload
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Parent was correctly forbidden from correcting a payment log.")


@pytest.mark.anyio
class TestPaymentLogsAPIGetListWithFilters:
    """Test class for GET /payment-logs/ with filter query parameters."""

    # --- Teacher Perspective ---

    async def test_list_logs_as_teacher_filter_by_parent(
        self, client: TestClient, test_teacher_orm: db_models.Teachers
    ):
        """A teacher filters payment logs by a specific parent."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"parent_id": str(TEST_PARENT_ID)}
        response = client.get("/payment-logs/", headers=headers, params=params)

        assert response.status_code == 200
        response_data = response.json()
        log_ids = {log["id"] for log in response_data}

        assert TEST_PAYMENT_LOG_ID in log_ids
        assert TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT not in log_ids
        print("Teacher successfully filtered payment logs by parent.")

    async def test_list_logs_as_teacher_filter_by_self(
        self, client: TestClient, test_teacher_orm: db_models.Teachers
    ):
        """A teacher filters payment logs by their own ID."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"teacher_id": str(TEST_TEACHER_ID)}
        response = client.get("/payment-logs/", headers=headers, params=params)

        assert response.status_code == 200
        response_data = response.json()
        log_ids = {log["id"] for log in response_data}

        assert TEST_PAYMENT_LOG_ID in log_ids
        assert TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT in log_ids
        assert TEST_PAYMENT_LOG_ID_UNRELATED not in log_ids
        print("Teacher successfully filtered payment logs by self.")

    async def test_list_logs_as_teacher_filter_by_other_teacher_is_forbidden(
        self, client: TestClient, test_teacher_orm: db_models.Teachers
    ):
        """A teacher is forbidden to filter payment logs by another teacher's ID."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"teacher_id": str(TEST_UNRELATED_TEACHER_ID)}
        response = client.get("/payment-logs/", headers=headers, params=params)

        assert response.status_code == 403
        assert "not authorized to view logs for this teacher" in response.json()["detail"]
        print("Teacher was correctly forbidden from filtering payment logs by another teacher.")

    # --- Parent Perspective ---

    async def test_list_logs_as_parent_filter_by_teacher(
        self, client: TestClient, test_parent_orm: db_models.Parents
    ):
        """A parent filters payment logs by a specific teacher."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"teacher_id": str(TEST_TEACHER_ID)}
        response = client.get("/payment-logs/", headers=headers, params=params)

        assert response.status_code == 200
        response_data = response.json()
        log_ids = {log["id"] for log in response_data}

        assert TEST_PAYMENT_LOG_ID in log_ids
        assert TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER not in log_ids
        print("Parent successfully filtered payment logs by teacher.")

    async def test_list_logs_as_parent_filter_by_self(
        self, client: TestClient, test_parent_orm: db_models.Parents
    ):
        """A parent filters payment logs by their own ID."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"parent_id": str(TEST_PARENT_ID)}
        response = client.get("/payment-logs/", headers=headers, params=params)

        assert response.status_code == 200
        response_data = response.json()
        log_ids = {log["id"] for log in response_data}

        assert TEST_PAYMENT_LOG_ID in log_ids
        assert TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER in log_ids
        assert TEST_PAYMENT_LOG_ID_UNRELATED not in log_ids
        print("Parent successfully filtered payment logs by self.")

    async def test_list_logs_as_parent_filter_by_other_parent_is_forbidden(
        self, client: TestClient, test_parent_orm: db_models.Parents
    ):
        """A parent is forbidden from filtering payment logs by another parent's ID."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"parent_id": str(TEST_UNRELATED_PARENT_ID)}
        response = client.get("/payment-logs/", headers=headers, params=params)

        assert response.status_code == 403
        assert "not authorized to view logs for this parent" in response.json()["detail"]
        print("Parent was correctly forbidden from filtering payment logs by another parent.")

