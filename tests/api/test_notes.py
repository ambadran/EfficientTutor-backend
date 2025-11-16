"""
Tests for the Notes API endpoints.
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.models import notes as notes_models
from src.efficient_tutor_backend.services.security import JWTHandler
from tests.constants import TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_ID, TEST_NOTE_ID, TEST_UNRELATED_TEACHER_ID


def auth_headers_for_user(user: db_models.Users) -> dict[str, str]:
    """Helper to create auth headers for a given user."""
    token = JWTHandler.create_access_token(subject=user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
class TestNotesAPIGetList:
    """Test class for the GET /notes/ endpoint."""

    async def test_list_notes_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that a teacher can list all their notes."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        response = client.get("/notes/", headers=headers)
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert isinstance(response_data, list)
        
        # The seed data creates one note for this teacher
        assert len(response_data) > 0
        
        # Structural validation of the first note
        note = response_data[0]
        assert "id" in note
        assert "name" in note
        assert "subject" in note
        assert "teacher" in note
        assert "student" in note
        assert note["teacher"]["id"] == str(TEST_TEACHER_ID)
        
        print("Teacher successfully listed their notes with valid structure.")

    async def test_list_notes_as_parent(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent can list notes for their children."""
        headers = auth_headers_for_user(test_parent_orm)
        
        response = client.get("/notes/", headers=headers)
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0
        
        note = response_data[0]
        assert note["student"]["id"] == str(TEST_STUDENT_ID)
        
        print("Parent successfully listed notes for their children.")

    async def test_list_notes_as_student(
        self,
        client: TestClient,
        test_student_orm: db_models.Students,
    ):
        """Test that a student can list their own notes."""
        headers = auth_headers_for_user(test_student_orm)
        
        response = client.get("/notes/", headers=headers)
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0
        
        note = response_data[0]
        assert note["student"]["id"] == str(TEST_STUDENT_ID)
        
        print("Student successfully listed their own notes.")


@pytest.mark.anyio
class TestNotesAPIPOST:
    """Test class for the POST /notes/ endpoint."""

    async def test_create_note_as_teacher(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that a teacher can successfully create a new note."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        note_payload = {
            "student_id": str(TEST_STUDENT_ID),
            "name": "API Created Note",
            "subject": "Math",
            "note_type": "HOMEWORK",
            "description": "This note was created via an API test."
        }
        
        response = client.post("/notes/", headers=headers, json=note_payload)
        
        assert response.status_code == 201
        
        response_data = response.json()
        assert response_data["name"] == "API Created Note"
        assert response_data["description"] == "This note was created via an API test."
        assert response_data["teacher"]["id"] == str(TEST_TEACHER_ID)
        assert response_data["student"]["id"] == str(TEST_STUDENT_ID)
        
        print("Teacher successfully created a new note.")

    async def test_create_note_as_parent_is_forbidden(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
    ):
        """Test that a parent is forbidden from creating a note."""
        headers = auth_headers_for_user(test_parent_orm)
        
        note_payload = {
            "student_id": str(TEST_STUDENT_ID),
            "name": "Forbidden Note",
            "subject": "Math",
            "note_type": "HOMEWORK",
        }
        
        response = client.post("/notes/", headers=headers, json=note_payload)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to perform this action."
        print("Parent was correctly forbidden from creating a note.")

    async def test_create_note_for_nonexistent_student_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that creating a note for a non-existent student fails gracefully."""
        headers = auth_headers_for_user(test_teacher_orm)
        
        note_payload = {
            "student_id": str(uuid4()), # Non-existent student
            "name": "Note for non-existent student",
            "subject": "Math",
            "note_type": "HOMEWORK",
        }
        
        response = client.post("/notes/", headers=headers, json=note_payload)
        
        # This test exposes a bug. The service should validate the student_id
        # and return a 404. Currently, it allows a DB IntegrityError, causing a 500.
        # We assert for the CORRECT behavior (404) to document the bug.
        assert response.status_code == 404
        assert "Student not found" in response.json()["detail"]
        print("Creating note for non-existent student failed as expected.")

