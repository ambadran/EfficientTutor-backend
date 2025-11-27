import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, EducationalSystemEnum
from src.efficient_tutor_backend.services.security import JWTHandler
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.services.user_service import TeacherService

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
        
        # Verify that teacher_specialties are loaded correctly
        assert teacher_data.teacher_specialties is not None
        assert isinstance(teacher_data.teacher_specialties, list)
        assert len(teacher_data.teacher_specialties) > 0
        assert isinstance(teacher_data.teacher_specialties[0], user_models.TeacherSpecialtyRead)

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

        # Validate the pydantic model and the presence of teacher_specialties
        teachers_read = [user_models.TeacherRead(**t) for t in response_data]
        
        first_teacher_with_specialties = next((t for t in teachers_read if t.teacher_specialties), None)
        assert first_teacher_with_specialties is not None
        assert isinstance(first_teacher_with_specialties.teacher_specialties, list)
        assert len(first_teacher_with_specialties.teacher_specialties) > 0
        assert isinstance(first_teacher_with_specialties.teacher_specialties[0], user_models.TeacherSpecialtyRead)

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
        
        # Ensure the specialties are still present after the update
        assert updated_data.teacher_specialties is not None
        assert isinstance(updated_data.teacher_specialties, list)

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
        
        # Ensure the specialties are still present after the update
        assert updated_data.teacher_specialties is not None
        assert isinstance(updated_data.teacher_specialties, list)

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


@pytest.mark.anyio
class TestTeacherSpecialtyAPI:
    """Test class for the teacher specialties endpoints."""

    async def test_add_specialty_as_owner_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test a teacher can add a new specialty to their own profile."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_teacher_orm)
        
        payload = {
            "subject": SubjectEnum.GEOGRAPHY.value,
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "grade": 10
        }

        print(f"Attempting to add specialty as owner {teacher_id}.")
        response = client.post(f"/teachers/{teacher_id}/specialties", headers=headers, json=payload)

        assert response.status_code == 201, response.json()
        updated_teacher = user_models.TeacherRead(**response.json())
        
        specialty_exists = any(
            s.subject == SubjectEnum.GEOGRAPHY and s.educational_system == EducationalSystemEnum.IGCSE
            for s in updated_teacher.teacher_specialties
        )
        assert specialty_exists
        print("Successfully added specialty as owner.")

    async def test_add_specialty_as_admin_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_admin_orm: db_models.Admins
    ):
        """Test an admin can add a new specialty to a teacher's profile."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_admin_orm)
        
        payload = {
            "subject": SubjectEnum.MATH.value,
            "educational_system": EducationalSystemEnum.NATIONAL_EG.value,
            "grade": 10
        }

        print(f"Admin attempting to add specialty to teacher {teacher_id}.")
        response = client.post(f"/teachers/{teacher_id}/specialties", headers=headers, json=payload)

        assert response.status_code == 201, response.json()
        updated_teacher = user_models.TeacherRead(**response.json())
        
        specialty_exists = any(
            s.subject == SubjectEnum.MATH and s.educational_system == EducationalSystemEnum.NATIONAL_EG
            for s in updated_teacher.teacher_specialties
        )
        assert specialty_exists
        print("Admin successfully added specialty to teacher.")

    async def test_add_duplicate_specialty_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test adding a specialty that already exists fails."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_teacher_orm)
        
        # This specialty is added in the seed data
        payload = {
            "subject": SubjectEnum.PHYSICS.value,
            "educational_system": EducationalSystemEnum.IGCSE.value,
            "grade": 10
        }

        print("Attempting to add a duplicate specialty.")
        response = client.post(f"/teachers/{teacher_id}/specialties", headers=headers, json=payload)

        assert response.status_code == 400
        assert response.json()["detail"] == "This specialty already exists for this teacher."
        print("Adding duplicate specialty failed as expected.")

    async def test_add_specialty_as_unauthorized_user_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents
    ):
        """Test a parent (unauthorized) cannot add a specialty."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_parent_orm)
        
        payload = {
            "subject": SubjectEnum.IT.value,
            "educational_system": EducationalSystemEnum.SAT.value,
            "grade": 10
        }

        print("Parent attempting to add specialty.")
        response = client.post(f"/teachers/{teacher_id}/specialties", headers=headers, json=payload)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to modify this profile."
        print("Unauthorized user was correctly forbidden from adding specialty.")

    async def test_delete_unused_specialty_as_owner_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Test a teacher can delete an unused specialty."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_teacher_orm)
        
        # First, add a specialty to delete
        add_payload = {
            "subject": SubjectEnum.BIOLOGY.value,
            "educational_system": EducationalSystemEnum.NATIONAL_KW.value,
            "grade": 10
        }
        add_response = client.post(f"/teachers/{teacher_id}/specialties", headers=headers, json=add_payload)
        assert add_response.status_code == 201
        added_specialty = next(
            s for s in add_response.json()["teacher_specialties"] if s["subject"] == add_payload["subject"]
        )
        specialty_id_to_delete = added_specialty["id"]

        print(f"Teacher attempting to delete own specialty {specialty_id_to_delete}.")
        delete_response = client.delete(f"/teachers/{teacher_id}/specialties/{specialty_id_to_delete}", headers=headers)

        assert delete_response.status_code == 204
        print("Successfully deleted own specialty.")

    async def test_delete_specialty_in_use_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test that deleting a specialty currently in use fails."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_teacher_orm)
        
        # This specialty is used by a student_subject in the seed data
        used_specialty = next(
            s for s in test_teacher_orm.teacher_specialties 
            if s.subject == SubjectEnum.PHYSICS.value and s.educational_system == EducationalSystemEnum.IGCSE.value
        )
        specialty_id_to_delete = used_specialty.id

        print(f"Attempting to delete a specialty that is in use: {specialty_id_to_delete}.")
        response = client.delete(f"/teachers/{teacher_id}/specialties/{specialty_id_to_delete}", headers=headers)

        assert response.status_code == 400
        assert "Cannot delete specialty as it is currently in use" in response.json()["detail"]
        print("Deleting specialty in use failed as expected.")

    async def test_delete_nonexistent_specialty_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
    ):
        """Test deleting a non-existent specialty fails with 404."""
        teacher_id = test_teacher_orm.id
        headers = auth_headers_for_user(test_teacher_orm)
        non_existent_id = uuid4()

        print(f"Attempting to delete non-existent specialty {non_existent_id}.")
        response = client.delete(f"/teachers/{teacher_id}/specialties/{non_existent_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Specialty not found."
        print("Deleting non-existent specialty failed as expected.")


@pytest.mark.anyio
class TestTeacherAPIGetBySpecialty:
    """Test class for the GET /teachers/by_specialty endpoint."""

    async def test_get_all_by_specialty_as_parent_success(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that a parent can successfully fetch teachers by specialty."""
        print("\n--- Testing GET /teachers/by_specialty as PARENT (Happy Path) ---")
        headers = auth_headers_for_user(test_parent_orm)
        
        # This query should match test_teacher_orm from the seed data
        query_params = {
            "subject": "Physics",
            "educational_system": "IGCSE",
            "grade": 10
        }

        response = client.get("/teachers/by_specialty", headers=headers, params=query_params)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) > 0
        
        # Verify the correct teacher is in the response
        teacher_ids = {t['id'] for t in response_data}
        assert str(test_teacher_orm.id) in teacher_ids
        
        # Verify the response model structure
        first_teacher = response_data[0]
        assert "teacher_specialties" in first_teacher
        assert isinstance(first_teacher["teacher_specialties"], list)

        print(f"--- Successfully found {len(response_data)} teachers for the query. ---")

    async def test_get_all_by_specialty_as_admin_success(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that an admin can successfully fetch teachers by specialty."""
        print("\n--- Testing GET /teachers/by_specialty as ADMIN (Happy Path) ---")
        headers = auth_headers_for_user(test_admin_orm)
        
        query_params = {
            "subject": "Physics",
            "educational_system": "IGCSE",
            "grade": 10
        }

        response = client.get("/teachers/by_specialty", headers=headers, params=query_params)

        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert len(response_data) > 0
        teacher_ids = {t['id'] for t in response_data}
        assert str(test_teacher_orm.id) in teacher_ids
        print(f"--- Successfully found {len(response_data)} teachers for the query. ---")

    async def test_get_all_by_specialty_no_match(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Tests an empty list is returned when no teachers match the specialty."""
        print("\n--- Testing GET /teachers/by_specialty with no matching specialty ---")
        headers = auth_headers_for_user(test_parent_orm)
        
        query_params = {
            "subject": "Geography",
            "educational_system": "IGCSE", # This combination doesn't exist
            "grade": 10
        }

        response = client.get("/teachers/by_specialty", headers=headers, params=query_params)

        assert response.status_code == 200, response.json()
        assert response.json() == []
        print("--- Correctly received an empty list for a non-matching specialty. ---")

    async def test_get_all_by_specialty_as_teacher_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that a teacher is forbidden from using this endpoint."""
        print("\n--- Testing GET /teachers/by_specialty as TEACHER (Forbidden) ---")
        headers = auth_headers_for_user(test_teacher_orm)
        query_params = {"subject": "Math", "educational_system": "SAT", "grade": 10}

        response = client.get("/teachers/by_specialty", headers=headers, params=query_params)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view this list."
        print(f"--- Correctly raised HTTPException: {response.status_code} ---")

    async def test_get_all_by_specialty_as_student_forbidden(
        self,
        client: TestClient,
        test_student_orm: db_models.Students
    ):
        """Tests that a student is forbidden from using this endpoint."""
        print("\n--- Testing GET /teachers/by_specialty as STUDENT (Forbidden) ---")
        headers = auth_headers_for_user(test_student_orm)
        query_params = {"subject": "Math", "educational_system": "SAT", "grade": 10}

        response = client.get("/teachers/by_specialty", headers=headers, params=query_params)

        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view this list."
        print(f"--- Correctly raised HTTPException: {response.status_code} ---")

    async def test_get_all_by_specialty_no_auth_fails(
        self,
        client: TestClient
    ):
        """Tests that an unauthenticated user cannot use the endpoint."""
        print("\n--- Testing GET /teachers/by_specialty without authentication ---")
        query_params = {"subject": "Math", "educational_system": "SAT", "grade": 10}
        
        response = client.get("/teachers/by_specialty", params=query_params)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("--- Unauthenticated request failed as expected. ---")

    async def test_get_all_by_specialty_invalid_query_params(
        self,
        client: TestClient,
        test_parent_orm: db_models.Parents
    ):
        """Tests that requests with invalid or missing query parameters fail."""
        print("\n--- Testing GET /teachers/by_specialty with invalid parameters ---")
        headers = auth_headers_for_user(test_parent_orm)
        
        # Missing 'grade'
        invalid_params = {
            "subject": "Math",
            "educational_system": "SAT"
        }
        
        response = client.get("/teachers/by_specialty", headers=headers, params=invalid_params)

        assert response.status_code == 422 # Unprocessable Entity
        print("--- Request with missing 'grade' failed with 422 as expected. ---")
        
        # Invalid value for 'subject'
        invalid_params_value = {
            "subject": "Quantum Physics",
            "educational_system": "SAT",
            "grade": 10
        }
        
        response_invalid_value = client.get("/teachers/by_specialty", headers=headers, params=invalid_params_value)
        
        assert response_invalid_value.status_code == 422 # Unprocessable Entity
        print("--- Request with invalid 'subject' value failed with 422 as expected. ---")


@pytest.mark.anyio
class TestTeacherAPIGetSpecialties:
    """Test class for the GET /teachers/{teacher_id}/specialties endpoint."""

    async def test_get_specialties_endpoint_as_owner_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that a teacher can successfully get their own specialties via the API."""
        print(f"\n--- Testing GET /teachers/{{teacher_id}}/specialties as OWNER ---")
        headers = auth_headers_for_user(test_teacher_orm)
        
        response = client.get(f"/teachers/{test_teacher_orm.id}/specialties", headers=headers)
        
        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == len(test_teacher_orm.teacher_specialties)
        
        # Basic structural check
        if response_data:
            assert "subject" in response_data[0]
            assert "educational_system" in response_data[0]
            assert "grade" in response_data[0]
        
        print(f"--- Successfully retrieved {len(response_data)} specialties for owner. ---")

    async def test_get_specialties_endpoint_as_admin_success(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_admin_orm: db_models.Admins
    ):
        """Tests that an admin can successfully get a teacher's specialties via the API."""
        print(f"\n--- Testing GET /teachers/{{teacher_id}}/specialties as ADMIN ---")
        headers = auth_headers_for_user(test_admin_orm)
        
        response = client.get(f"/teachers/{test_teacher_orm.id}/specialties", headers=headers)
        
        assert response.status_code == 200, response.json()
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == len(test_teacher_orm.teacher_specialties)
        print(f"--- Admin successfully retrieved {len(response_data)} specialties. ---")

    async def test_get_specialties_endpoint_as_unrelated_teacher_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_unrelated_teacher_orm: db_models.Teachers
    ):
        """Tests that an unrelated teacher is forbidden from getting specialties."""
        print(f"\n--- Testing GET /teachers/{{teacher_id}}/specialties as UNRELATED TEACHER (Forbidden) ---")
        headers = auth_headers_for_user(test_unrelated_teacher_orm)
        
        response = client.get(f"/teachers/{test_teacher_orm.id}/specialties", headers=headers)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view these specialties."
        print(f"--- Correctly raised HTTPException: {response.status_code} ---")

    async def test_get_specialties_endpoint_as_parent_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_parent_orm: db_models.Parents
    ):
        """Tests that a parent is forbidden from getting specialties."""
        print(f"\n--- Testing GET /teachers/{{teacher_id}}/specialties as PARENT (Forbidden) ---")
        headers = auth_headers_for_user(test_parent_orm)
        
        response = client.get(f"/teachers/{test_teacher_orm.id}/specialties", headers=headers)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view these specialties."
        print(f"--- Correctly raised HTTPException: {response.status_code} ---")

    async def test_get_specialties_endpoint_as_student_forbidden(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers,
        test_student_orm: db_models.Students
    ):
        """Tests that a student is forbidden from getting specialties."""
        print(f"\n--- Testing GET /teachers/{{teacher_id}}/specialties as STUDENT (Forbidden) ---")
        headers = auth_headers_for_user(test_student_orm)
        
        response = client.get(f"/teachers/{test_teacher_orm.id}/specialties", headers=headers)
        
        assert response.status_code == 403
        assert response.json()["detail"] == "You do not have permission to view these specialties."
        print(f"--- Correctly raised HTTPException: {response.status_code} ---")

    async def test_get_specialties_endpoint_no_auth_fails(
        self,
        client: TestClient,
        test_teacher_orm: db_models.Teachers
    ):
        """Tests that an unauthenticated user cannot get specialties."""
        print("\n--- Testing GET /teachers/{teacher_id}/specialties without authentication ---")
        
        response = client.get(f"/teachers/{test_teacher_orm.id}/specialties")
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        print("--- Unauthenticated request failed as expected. ---")

    async def test_get_specialties_endpoint_not_found(
        self,
        client: TestClient,
        test_admin_orm: db_models.Admins
    ):
        """Tests that requesting specialties for a non-existent teacher fails with 404."""
        print("\n--- Testing GET /teachers/{teacher_id}/specialties for non-existent teacher ---")
        headers = auth_headers_for_user(test_admin_orm)
        non_existent_id = uuid4()
        
        response = client.get(f"/teachers/{non_existent_id}/specialties", headers=headers)
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Teacher not found."
        print(f"--- Correctly raised HTTPException: {response.status_code} ---")




