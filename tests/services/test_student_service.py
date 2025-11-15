import pytest
from uuid import UUID
from fastapi import HTTPException
from datetime import time
from decimal import Decimal

# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.user_service import StudentService
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.database.db_enums import UserRole, SubjectEnum
from tests.constants import TEST_TEACHER_ID, TEST_PARENT_ID, TEST_STUDENT_ID, TEST_UNRELATED_TEACHER_ID

from pprint import pp as pprint


@pytest.mark.anyio
class TestStudentService:

    # --- Tests for get_all ---

    async def test_get_all_as_teacher(
        self, 
        student_service: StudentService, 
        test_teacher_orm: db_models.Users, # <-- Use the new fixture
        test_student_orm: db_models.Users  # <-- Use the new fixture
    ):
        """Tests that a TEACHER can get all students."""
        students = await student_service.get_all(current_user=test_teacher_orm)
       
        print(f"Found {len(students)} students for teacher '{test_teacher_orm.first_name} {test_teacher_orm.last_name}':\n{[student.first_name for student in students]}")

        assert len(students) >= 1
        assert type(students[0]) == db_models.Students
        assert any(s.id == test_student_orm.id for s in students)
        
        # Verify that nested relationships are loaded to prevent MissingGreenlet errors
        assert students[0].student_subjects is not None
        assert students[0].student_availability_intervals is not None

    async def test_get_all_as_parent(
        self, 
        student_service: StudentService, 
        test_parent_orm: db_models.Users, # <-- Use the new fixture
        test_student_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests that a PARENT can get all students."""
        students = await student_service.get_all(current_user=test_parent_orm)

        print(f"Found {len(students)} students for Parent '{test_parent_orm.first_name} {test_parent_orm.last_name}':\n{[student.first_name for student in students]}")
        
        assert len(students) >= 1
        assert type(students[0]) == db_models.Students
        assert any(s.id == test_student_orm.id for s in students)

        # Verify that nested relationships are loaded to prevent MissingGreenlet errors
        assert students[0].student_subjects is not None
        assert students[0].student_availability_intervals is not None

    async def test_get_all_as_student_forbidden(
        self, 
        student_service: StudentService, 
        test_student_orm: db_models.Users # <-- Use the new fixture
    ):
        """Tests that a STUDENT cannot get all students (HTTP 403)."""
        with pytest.raises(HTTPException) as e:
            await student_service.get_all(current_user=test_student_orm)
        
        assert e.value.status_code == 403

    # --- Tests for create_student ---

    async def test_create_student_as_teacher_happy_path(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests successful student creation by a Teacher."""
        print("\n--- Testing create_student as TEACHER (Happy Path) ---")
        
        create_model = user_models.StudentCreate(**valid_student_data)
        
        new_student = await student_service.create_student(create_model, test_teacher_orm)
        
        assert isinstance(new_student, user_models.StudentRead)
        assert new_student.email == create_model.email
        assert new_student.first_name == "Pytest"
        assert new_student.parent_id == TEST_PARENT_ID
        
        # Verify relational data
        assert len(new_student.student_subjects) == 1
        assert new_student.student_subjects[0].subject == SubjectEnum.PHYSICS
        assert new_student.student_subjects[0].shared_with_student_ids == [TEST_STUDENT_ID]
        
        assert len(new_student.student_availability_intervals) == 1
        assert new_student.student_availability_intervals[0].day_of_week == 1

        # Check the underlying DB object for generated password
        db_student = await student_service.get_user_by_id(new_student.id)
        assert db_student.generated_password is not None

        print("--- Successfully created student (API model) ---")
        pprint(new_student.model_dump())

    async def test_create_student_as_parent_happy_path(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests successful student creation by a Parent."""
        print("\n--- Testing create_student as PARENT (Happy Path) ---")
        
        # Ensure the parent is creating their own child
        valid_student_data["parent_id"] = test_parent_orm.id
        valid_student_data["email"] = "pytest.student.parent@example.com" # different email to avoid conflict
        create_model = user_models.StudentCreate(**valid_student_data)
        
        new_student = await student_service.create_student(create_model, test_parent_orm)
        
        assert isinstance(new_student, user_models.StudentRead)
        assert new_student.email == create_model.email
        print("--- Successfully created student (API model) ---")
        pprint(new_student.model_dump())

    async def test_create_student_as_parent_mismatched_parent_id(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Parent cannot create a student for a parent_id that does not match their own."""
        print("\n--- Testing create_student as PARENT (Mismatched Parent ID) ---")

        # Set parent_id to a different parent (e.g., TEST_TEACHER_ID, which is not a parent)
        # or a random UUID that doesn't match test_parent_orm.id
        valid_student_data["parent_id"] = TEST_TEACHER_ID # This is guaranteed to be a different ID
        valid_student_data["email"] = "mismatched.parent@example.com" # different email to avoid conflict
        create_model = user_models.StudentCreate(**valid_student_data)

        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_parent_orm)

        assert e.value.status_code == 403
        assert "Parents can only create students for themselves." in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_student_as_student_forbidden(
        self,
        student_service: StudentService,
        test_student_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Student is FORBIDDEN from creating a student."""
        print("\n--- Testing create_student as STUDENT (Forbidden) ---")
        
        # Ensure the test email isn't used by other tests
        valid_student_data["email"] = "student.forbidden@example.com" 
        create_model = user_models.StudentCreate(**valid_student_data)
        
        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_student_orm)
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_student_duplicate_email(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that creating a student with an existing email fails."""
        print("\n--- Testing create_student with duplicate email ---")
        
        valid_student_data["email"] = test_student_orm.email  # Use an existing email
        create_model = user_models.StudentCreate(**valid_student_data)
        
        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_teacher_orm)
            
        assert e.value.status_code == 400
        assert "Email already registered" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_student_non_existent_parent(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests creating a student with a parent_id that does not exist."""
        print("\n--- Testing create_student with non-existent parent ---")
        
        valid_student_data["email"] = "nonexistent.parent@example.com" # different email to avoid conflict
        valid_student_data["parent_id"] = UUID(int=0) # Random, non-existent UUID
        create_model = user_models.StudentCreate(**valid_student_data)
        
        with pytest.raises(HTTPException) as e:
            await student_service.create_student(create_model, test_teacher_orm)
                
            assert e.value.status_code == 404
            assert "not found" in e.value.detail
            print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_student_with_minimal_data(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests creating a student with empty subjects and availability."""
        print("\n--- Testing create_student with minimal data ---")
        
        valid_student_data["student_subjects"] = []
        valid_student_data["student_availability_intervals"] = []
        valid_student_data["email"] = "minimal.student@example.com"
        
        create_model = user_models.StudentCreate(**valid_student_data)
        
        new_student = await student_service.create_student(create_model, test_teacher_orm)
        
        assert isinstance(new_student, user_models.StudentRead)
        assert new_student.email == "minimal.student@example.com"
        assert len(new_student.student_subjects) == 0
        assert len(new_student.student_availability_intervals) == 0
        
        print("--- Successfully created student with minimal data ---")
        pprint(new_student.model_dump())

    # --- Tests for update_student ---

    async def test_update_student_as_teacher(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that a Teacher can successfully update a student's fields."""
        print("\n--- Testing update_student as TEACHER ---")
        
        update_payload = user_models.StudentUpdate(
            first_name="UpdatedByTeacher",
            grade=11
        )
        
        updated_student = await student_service.update_student(
            student_id=test_student_orm.id,
            update_data=update_payload,
            current_user=test_teacher_orm
        )
        
        assert isinstance(updated_student, user_models.StudentRead)
        assert updated_student.id == test_student_orm.id
        assert updated_student.first_name == "UpdatedByTeacher"
        assert updated_student.grade == 11
        # Ensure other fields are unchanged
        assert updated_student.last_name == test_student_orm.last_name
        
        print("--- Successfully updated student (API model) ---")
        pprint(updated_student.model_dump())

    async def test_update_student_as_parent(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that a Parent can successfully update their own child."""
        print("\n--- Testing update_student as PARENT ---")
        
        # Pre-condition check
        assert test_student_orm.parent_id == test_parent_orm.id

        update_payload = user_models.StudentUpdate(
            cost=Decimal("99.99")
        )
        
        updated_student = await student_service.update_student(
            student_id=test_student_orm.id,
            update_data=update_payload,
            current_user=test_parent_orm
        )
        
        assert isinstance(updated_student, user_models.StudentRead)
        assert updated_student.cost == Decimal("99.99")
        
        print("--- Successfully updated student (API model) ---")
        pprint(updated_student.model_dump())

    async def test_update_student_as_unrelated_parent_forbidden(
        self,
        student_service: StudentService,
        test_unrelated_parent_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that an unrelated Parent is FORBIDDEN from updating a student."""
        print("\n--- Testing update_student as UNRELATED PARENT (Forbidden) ---")
        
        update_payload = user_models.StudentUpdate(first_name="ForbiddenUpdate")
        
        with pytest.raises(HTTPException) as e:
            await student_service.update_student(
                student_id=test_student_orm.id,
                update_data=update_payload,
                current_user=test_unrelated_parent_orm
            )
        
        assert e.value.status_code == 403
        assert "only update their own children" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_student_as_student_forbidden(
        self,
        student_service: StudentService,
        test_student_orm: db_models.Students
    ):
        """Tests that a Student is FORBIDDEN from updating their own profile."""
        print("\n--- Testing update_student as STUDENT (Forbidden) ---")
        
        update_payload = user_models.StudentUpdate(first_name="ForbiddenUpdate")
        
        with pytest.raises(HTTPException) as e:
            await student_service.update_student(
                student_id=test_student_orm.id,
                update_data=update_payload,
                current_user=test_student_orm
            )
        
        assert e.value.status_code == 403
        assert "permission to update students" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_update_student_replace_nested_lists(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that updating nested lists (subjects, availability) replaces them entirely."""
        print("\n--- Testing update_student replaces nested lists ---")
        
        # 1. ARRANGE: Fetch a fresh, fully-loaded student object to avoid lazy-loading issues
        student_id_to_update = test_student_orm.id
        student_to_update = await student_service.get_user_by_id(student_id_to_update)
        assert student_to_update is not None

        # Pre-condition: Ensure the student has existing subjects/availability
        assert len(student_to_update.student_subjects) > 0
        assert len(student_to_update.student_availability_intervals) > 0

        new_subjects = [
            user_models.StudentSubjectWrite(subject=SubjectEnum.CHEMISTRY,
                                            lessons_per_week=3,
                                            teacher_id=TEST_UNRELATED_TEACHER_ID)
        ]
        new_availability = [
            user_models.StudentAvailabilityIntervalWrite(day_of_week=7, start_time=time(10,0), end_time=time(12,0), availability_type="sleep")
        ]
        
        update_payload = user_models.StudentUpdate(
            student_subjects=new_subjects,
            student_availability_intervals=new_availability
        )
        
        # 2. ACT
        updated_student = await student_service.update_student(
            student_id=student_id_to_update,
            update_data=update_payload,
            current_user=test_teacher_orm
        )
        
        # 3. ASSERT
        assert len(updated_student.student_subjects) == 1
        assert updated_student.student_subjects[0].subject == SubjectEnum.CHEMISTRY
        assert updated_student.student_subjects[0].lessons_per_week == 3
        assert updated_student.student_subjects[0].teacher_id == TEST_UNRELATED_TEACHER_ID
        
        assert len(updated_student.student_availability_intervals) == 1
        assert updated_student.student_availability_intervals[0].day_of_week == 7
        assert updated_student.student_availability_intervals[0].availability_type == "sleep"
        
        print("--- Successfully replaced nested lists ---")
        pprint(updated_student.model_dump())

    async def test_update_student_not_found(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that updating a non-existent student raises a 404."""
        print("\n--- Testing update_student for non-existent ID ---")
        
        update_payload = user_models.StudentUpdate(first_name="NotFound")
        
        with pytest.raises(HTTPException) as e:
            await student_service.update_student(
                student_id=UUID(int=0),
                update_data=update_payload,
                current_user=test_teacher_orm
            )
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    # --- Tests for delete_student ---

    async def test_delete_student_as_parent(
        self,
        student_service: StudentService,
        test_parent_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Parent can delete their own child."""
        print("\n--- Testing delete_student as PARENT ---")
        
        # 1. Create a new student to delete
        valid_student_data["email"] = "to.be.deleted.by.parent@example.com"
        valid_student_data["parent_id"] = test_parent_orm.id
        create_model = user_models.StudentCreate(**valid_student_data)
        student_to_delete = await student_service.create_student(create_model, test_parent_orm)
        
        # 2. Act: Delete the student
        success = await student_service.delete_student(student_to_delete.id, test_parent_orm)
        assert success is True
        await student_service.db.commit() # Commit the deletion
        
        # 3. Verify: The student should now be gone
        deleted_user = await student_service.get_user_by_id(student_to_delete.id)
        assert deleted_user is None
        print(f"--- Successfully deleted student {student_to_delete.id} ---")

    async def test_delete_student_as_teacher(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users,
        valid_student_data: dict
    ):
        """Tests that a Teacher can delete a student."""
        print("\n--- Testing delete_student as TEACHER ---")
        
        # 1. Create a new student to delete
        valid_student_data["email"] = "to.be.deleted.by.teacher@example.com"
        create_model = user_models.StudentCreate(**valid_student_data)
        student_to_delete = await student_service.create_student(create_model, test_teacher_orm)
        
        # 2. Act: Delete the student
        success = await student_service.delete_student(student_to_delete.id, test_teacher_orm)
        assert success is True
        await student_service.db.commit() # Commit the deletion
        
        # 3. Verify: The student should now be gone
        deleted_user = await student_service.get_user_by_id(student_to_delete.id)
        assert deleted_user is None
        print(f"--- Successfully deleted student {student_to_delete.id} ---")

    async def test_delete_student_as_unrelated_parent_forbidden(
        self,
        student_service: StudentService,
        test_unrelated_parent_orm: db_models.Users,
        test_student_orm: db_models.Students
    ):
        """Tests that an unrelated Parent is FORBIDDEN from deleting a student."""
        print("\n--- Testing delete_student as UNRELATED PARENT (Forbidden) ---")
        
        with pytest.raises(HTTPException) as e:
            await student_service.delete_student(test_student_orm.id, test_unrelated_parent_orm)
            
        assert e.value.status_code == 403
        assert "only delete their own children" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_delete_student_as_student_forbidden(
        self,
        student_service: StudentService,
        test_student_orm: db_models.Students
    ):
        """Tests that a Student is FORBIDDEN from deleting themselves."""
        print("\n--- Testing delete_student as STUDENT (Forbidden) ---")
        
        with pytest.raises(HTTPException) as e:
            await student_service.delete_student(test_student_orm.id, test_student_orm)
            
        assert e.value.status_code == 403
        assert "permission to delete students" in e.value.detail
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_delete_student_not_found(
        self,
        student_service: StudentService,
        test_teacher_orm: db_models.Users
    ):
        """Tests that deleting a non-existent student raises a 404."""
        print("\n--- Testing delete_student for non-existent ID ---")
        
        with pytest.raises(HTTPException) as e:
            await student_service.delete_student(UUID(int=0), test_teacher_orm)
            
        assert e.value.status_code == 404
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")


