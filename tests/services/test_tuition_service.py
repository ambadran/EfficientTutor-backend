'''

'''
import pytest
from uuid import UUID
from fastapi import HTTPException
# --- Import models and services ---
from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.services.tuition_service import TuitionService
# --- Import Test Constants ---
from tests.constants import TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_ID

from pprint import pp as pprint

@pytest.mark.anyio
class TestTuitionService:

    ### Tests for get_tuition_by_id ###

    async def test_get_tuition_by_id(
        self,
        tuition_service: TuitionService,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests fetching a single tuition template by its ID."""
        # Use the fixture to get a known tuition
        tuition = await tuition_service.get_tuition_by_id(test_tuition_orm.id)
       
        print(f"\n--- Found Tuition by ID ({test_tuition_orm.id}) ---")
        pprint(tuition.__dict__)

        assert tuition is not None
        assert tuition.id == test_tuition_orm.id

    async def test_get_tuition_by_id_not_found(
        self,
        tuition_service: TuitionService
    ):
        """Tests that None is returned for a non-existent tuition ID."""
        tuition = await tuition_service.get_tuition_by_id(UUID(int=0)) # Random UUID
        assert tuition is None

    ### Tests for get_all_tuitions ###

    async def test_get_all_as_teacher(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests that a TEACHER can successfully fetch all tuitions.
        The service should return all tuitions associated with this teacher.
        """
        print(f"\n--- Testing get_all_tuitions as TEACHER ({test_teacher_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions(current_user=test_teacher_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Total Tuitions for Teacher ---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)
        else:
            print("--- No tuitions found for this teacher in the test data. ---")
        # --- End Logging ---

    async def test_get_all_as_parent(
        self,
        tuition_service: TuitionService,
        test_parent_orm: db_models.Users
    ):
        """
        Tests that a PARENT can successfully fetch their tuitions.
        The service should return only tuitions relevant to this parent.
        """
        print(f"\n--- Testing get_all_tuitions as PARENT ({test_parent_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions(current_user=test_parent_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        # We can't know the exact count, but we know the call succeeded.
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Tuitions for Parent ---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)
        else:
            print("--- No tuitions found for this parent in the test data. ---")
        # --- End Logging ---

    async def test_get_all_as_student(
        self,
        tuition_service: TuitionService,
        test_student_orm: db_models.Users
    ):
        """
        Tests that a STUDENT can successfully fetch their tuitions.
        The service should return only tuitions relevant to this student.
        """
        print(f"\n--- Testing get_all_tuitions as STUDENT ({test_student_orm.first_name}) ---")

        tuitions = await tuition_service.get_all_tuitions(current_user=test_student_orm)

        # --- Assertions ---
        assert isinstance(tuitions, list)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Tuitions for Student ---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)

    ### Tests for regenerate_all_tuitions ###

    async def test_regenerate_all_tuitions(
        self,
        tuition_service: TuitionService
    ):
        """
        Tests that the regeneration process runs and returns True.
        This test confirms the method call succeeds.
        """
        #TODO:
        pass

    ### Tests for _generate_deterministic_id ###
    
    def test_generate_deterministic_id(
        self,
        tuition_service_sync: TuitionService # Request the service to get the method
    ):
        """
        Tests the internal ID generation logic.
        Note: This is a regular 'def' test, not 'async def'.
        """
        # For clarity, assign it to the name the rest of the
        # test expects, or just use tuition_service_sync directly.
        tuition_service = tuition_service_sync

        # Define two lists of student IDs, sorted to ensure order doesn't matter
        student_ids_1 = sorted([TEST_STUDENT_ID, TEST_PARENT_ID]) # Just using 2 IDs
        student_ids_2 = sorted([TEST_STUDENT_ID]) # A different list
        
        # --- Case 1: Same inputs should produce the same UUID ---
        uuid_1 = tuition_service._generate_deterministic_id(
            subject="Math",
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        uuid_2 = tuition_service._generate_deterministic_id(
            subject="Math",
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        assert isinstance(uuid_1, UUID)
        assert uuid_1 == uuid_2, "Same inputs did not produce the same UUID"
        
        # --- Case 2: Different student list should produce a different UUID ---
        uuid_3 = tuition_service._generate_deterministic_id(
            subject="Math",
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_2 # <-- Different list
        )
        
        assert uuid_1 != uuid_3, "Different student list produced the same UUID"
        
        # --- Case 3: Different subject should produce a different UUID ---
        uuid_4 = tuition_service._generate_deterministic_id(
            subject="Physics", # <-- Different subject
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        assert uuid_1 != uuid_4, "Different subject produced the same UUID"
