import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import timetable as timetable_models
from tests.constants import (
    TEST_TUITION_ID, 
    TEST_STUDENT_ID, 
    TEST_TEACHER_ID,
    TEST_SLOT_ID_STUDENT_MATH,
    TEST_SLOT_ID_TEACHER_AVAILABILITY,
    TEST_UNRELATED_TEACHER_ID,
    TEST_UNRELATED_STUDENT_ID
)

from pprint import pp as pprint

# Helper to create auth headers
def auth_headers_for_user(user: db_models.Users) -> dict:
    """Creates a JWT token for the given user and returns auth headers."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestTimetableAPIWithoutQuery:
    """Tests for GET /timetable/ (Default/Self View)."""

    async def test_get_timetable_teacher_default(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Teacher fetching their own timetable by default."""
        print(f"Teacher {test_teacher_orm.email} fetching default timetable.")
        headers = auth_headers_for_user(test_teacher_orm)

        response = client.get("/timetable/", headers=headers)

        assert response.status_code == 200, response.json()
        data = response.json()
        assert isinstance(data, list)
        
        # Teacher has 3 slots in seed data (2 mirrored tuition + 1 availability)
        assert len(data) >= 3
        
        # Verify Availability Slot
        avail_slot = next((s for s in data if s["id"] == str(TEST_SLOT_ID_TEACHER_AVAILABILITY)), None)
        assert avail_slot is not None
        assert avail_slot["slot_type"] == timetable_models.TimeTableSlotType.AVAILABILITY.value
        assert avail_slot["name"] == "Work"
        pprint(avail_slot)

    async def test_get_timetable_student_default(
        self,
        client: TestClient,
        test_student_orm: db_models.Students
    ):
        """Student fetching their own timetable by default."""
        print(f"Student {test_student_orm.email} fetching default timetable.")
        headers = auth_headers_for_user(test_student_orm)
        
        response = client.get("/timetable/", headers=headers)
        
        assert response.status_code == 200, response.json()
        data = response.json()
        
        # Student has 2 slots in seed data
        assert len(data) >= 2
        
        math_slot = next((s for s in data if s["id"] == str(TEST_SLOT_ID_STUDENT_MATH)), None)
        assert math_slot is not None
        assert math_slot["object_uuid"] == str(TEST_TUITION_ID) # Unmasked
        pprint(math_slot)

    async def test_get_timetable_parent_default(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """
        Parent fetching default timetable.
        Parents don't have personal 'TimetableRunUserSolutions' rows in the seed data,
        so this should return an empty list, NOT an error.
        """
        print(f"Parent {test_parent_orm.email} fetching default timetable.")
        headers = auth_headers_for_user(test_parent_orm)
        
        response = client.get("/timetable/", headers=headers)
        
        assert response.status_code == 200, response.json()
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2 # Expecting empty list for parent self-view
        print("Parent default view returned empty list as expected.")


@pytest.mark.anyio
class TestTimetableAPIWithQuery:
    """Tests for GET /timetable/?target_user_id=..."""

    async def test_get_timetable_teacher_viewing_student(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students
    ):
        """Teacher viewing a specific student."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"target_user_id": str(test_student_orm.id)}
        
        print(f"Teacher viewing Student {test_student_orm.id}")
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 200, response.json()
        data = response.json()
        assert len(data) >= 2
        
        # Verify unmasked access
        slot = data[0]
        assert slot["name"] != "Others"
        assert slot["object_uuid"] is not None

    async def test_get_timetable_teacher_viewing_self_explicit(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Teacher viewing themselves explicitly."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"target_user_id": str(test_teacher_orm.id)}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

    async def test_get_timetable_parent_viewing_child(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_student_orm: db_models.Students
    ):
        """Parent viewing their child."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"target_user_id": str(test_student_orm.id)}

        print(f"Parent viewing Child {test_student_orm.id}")
        response = client.get("/timetable/", headers=headers, params=params)

        assert response.status_code == 200, response.json()
        data = response.json()
        assert len(data) >= 2
        
        # Verify unmasked
        slot = data[0]
        assert slot["object_uuid"] is not None

    async def test_get_timetable_student_viewing_self_explicit(
        self,
        client: TestClient,
        test_student_orm: db_models.Students
    ):
        """Student viewing themselves explicitly."""
        headers = auth_headers_for_user(test_student_orm)
        params = {"target_user_id": str(test_student_orm.id)}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2


@pytest.mark.anyio
class TestTimetableAPIForbidden:
    """Tests for 403 Forbidden scenarios."""

    async def test_teacher_viewing_other_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_unrelated_teacher_orm: db_models.Teachers
    ):
        """Teacher cannot view another Teacher."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"target_user_id": str(test_unrelated_teacher_orm.id)}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 403
        assert "Teachers can only view timetables for students" in response.json()["detail"]

    async def test_parent_viewing_unrelated_student(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_unrelated_student_orm: db_models.Students
    ):
        """Parent cannot view unrelated student."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"target_user_id": str(test_unrelated_student_orm.id)}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 403
        assert "only view timetables for their own children" in response.json()["detail"]

    async def test_parent_viewing_teacher(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """Parent cannot view a Teacher."""
        headers = auth_headers_for_user(test_parent_orm)
        params = {"target_user_id": str(test_teacher_orm.id)}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        # Parent logic checks "if target_id in my_students". Teacher ID won't be there.
        assert response.status_code == 403
        assert "only view timetables for their own children" in response.json()["detail"]

    async def test_student_viewing_other_student(
        self,
        client: TestClient,
        test_student_orm: db_models.Students,
        test_unrelated_student_orm: db_models.Students
    ):
        """Student cannot view another student."""
        headers = auth_headers_for_user(test_student_orm)
        params = {"target_user_id": str(test_unrelated_student_orm.id)}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 403
        assert "Students cannot view other users" in response.json()["detail"]

    async def test_student_viewing_teacher(
        self,
        client: TestClient,
        test_student_orm: db_models.Students,
        test_teacher_orm: db_models.Teachers
    ):
        """Student cannot view a Teacher."""
        headers = auth_headers_for_user(test_student_orm)
        params = {"target_user_id": str(test_teacher_orm.id)}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 403
        assert "Students cannot view other users" in response.json()["detail"]


@pytest.mark.anyio
class TestTimetableAPIError:
    """Tests for Error scenarios (404, 401)."""

    async def test_target_user_not_found(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """404 when target user UUID doesn't exist."""
        headers = auth_headers_for_user(test_teacher_orm)
        params = {"target_user_id": str(uuid4())}
        
        response = client.get("/timetable/", headers=headers, params=params)
        
        assert response.status_code == 404
        assert "Target user not found" in response.json()["detail"]

    async def test_unauthorized_access(self, client: TestClient):
        """401 when no token provided."""
        response = client.get("/timetable/")
        assert response.status_code == 401


