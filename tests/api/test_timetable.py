import pytest
from fastapi.testclient import TestClient
from typing import List

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import timetable as timetable_models
from tests.constants import TEST_TUITION_ID, TEST_STUDENT_ID

from pprint import pp as pprint

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestTimetableAPI:
    """Test class for the Timetable API endpoint."""

    async def test_get_timetable_as_teacher_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test successfully fetching the timetable for a teacher."""
        print(f"Attempting to fetch timetable as teacher: {test_teacher_orm.email}")
        headers = auth_headers_for_user(test_teacher_orm)

        response = client.get("/timetable/", headers=headers)

        assert response.status_code == 200, response.json()
        
        response_data = response.json()
        assert isinstance(response_data, list)
        
        # The seed data creates tuitions, so the list should not be empty
        assert len(response_data) > 0, "Timetable for teacher should not be empty based on seed data."

        # Validate the structure of the first item
        timetable_entry = timetable_models.ScheduledTuitionReadForTeacher(**response_data[0])

        pprint(timetable_entry.model_dump())
        
        # Assert that the tuition ID from the response matches our test tuition
        assert timetable_entry.tuition.id == TEST_TUITION_ID
        
        # Assert that the financial charges are present and for the correct student
        assert len(timetable_entry.tuition.charges) > 0
        assert timetable_entry.tuition.charges[0].student.id == TEST_STUDENT_ID
        
        print(f"Successfully fetched and validated timetable for teacher {test_teacher_orm.email}")

    async def test_get_timetable_as_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_student_orm: db_models.Students
    ):
        """Test successfully fetching the timetable for a parent."""
        print(f"Attempting to fetch timetable as parent: {test_parent_orm.email}")
        headers = auth_headers_for_user(test_parent_orm)

        response = client.get("/timetable/", headers=headers)

        assert response.status_code == 200, response.json()
        
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0, "Timetable for parent should not be empty based on seed data."

        # Validate the structure of the first item
        timetable_entry = timetable_models.ScheduledTuitionReadForParent(**response_data[0])
        
        # Assert that the parent is being charged and their child is in the list
        assert timetable_entry.tuition.charge > 0
        student_full_name = f"{test_student_orm.first_name} {test_student_orm.last_name}"
        assert student_full_name in timetable_entry.tuition.attendee_names

        print(f"Successfully fetched and validated timetable for parent {test_parent_orm.email}")

    async def test_get_timetable_as_student_success(
        self,
        client: TestClient,
        test_student_orm: db_models.Students
    ):
        """Test successfully fetching the timetable for a student."""
        print(f"Attempting to fetch timetable as student: {test_student_orm.email}")
        headers = auth_headers_for_user(test_student_orm)

        response = client.get("/timetable/", headers=headers)

        assert response.status_code == 200, response.json()
        
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0, "Timetable for student should not be empty based on seed data."

        # Validate the structure of the first item
        timetable_entry = timetable_models.ScheduledTuitionReadForStudent(**response_data[0])

        # Assert that the student's own name is in the list of attendees
        student_full_name = f"{test_student_orm.first_name} {test_student_orm.last_name}"
        assert student_full_name in timetable_entry.tuition.attendee_names

        print(f"Successfully fetched and validated timetable for student {test_student_orm.email}")

    async def test_get_timetable_as_admin_returns_empty_list(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Test that an admin receives """
        print(f"Attempting to fetch timetable as admin: {test_admin_orm.email}")
        headers = auth_headers_for_user(test_admin_orm)

        response = client.get("/timetable/", headers=headers)

        assert response.status_code == 200, response.json()
        
        response_data = response.json()
        # assert response_data == []
        #TODO: continue this test when the authorization of admin role is finished

    async def test_get_timetable_no_auth_fails(
        self,
        client: TestClient
    ):
        """Test that an unauthenticated user cannot fetch a timetable."""
        print("Attempting to fetch timetable without authentication.")
        
        response = client.get("/timetable/")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("Unauthenticated request failed as expected.")
